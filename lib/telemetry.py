import numpy as np
import pandas as pd
import os
from datetime import datetime, timedelta
from google.cloud import bigquery

class TelemetryClient:
  def __init__(self, dataDir, skipCache):
    self.client = bigquery.Client()
    self.dataDir = dataDir
    self.skipCache = skipCache

  def generateEventsQuery(self, config, branch, date=None):
      if date:
        date_conditions = f"""AND DATE(submission_timestamp) = DATE('{date}')"""
      else:
        date_conditions = f"""AND DATE(submission_timestamp) >= DATE('{config['startDate']}')
                    AND DATE(submission_timestamp) <= DATE('{config['endDate']}')"""

      field_selections = ""
      for field in config['pageload_event_fields']:
        field_selections = field_selections + \
              f"""                    SAFE_CAST((SELECT value FROM UNNEST(event.extra) WHERE key = '{field}') AS float64) AS {field},\n"""

      query = f"""WITH eventdata AS (
                  SELECT
                    client_info.app_build AS app_build,
                    client_info.app_display_Version AS app_version,
                    metadata.geo.country AS country,
                    metadata.user_agent.os AS os,
                    metadata.user_agent.version AS os_version,
                    {field_selections}
                  FROM
                    `moz-fx-data-shared-prod.firefox_desktop.pageload`
                  CROSS JOIN
                    UNNEST(events) AS event
                  WHERE 
                    normalized_channel = "{config['channel']}"
                    {date_conditions}
                    AND mozfun.map.get_key(ping_info.experiments, "{config['slug']}").branch = "{branch}"
                  )
                  SELECT 
                    *
                  FROM 
                    eventdata
                  WHERE
                    load_time > 0
                    AND response_time > 0
                    AND fcp_time > 0
                """
      
      #if "queries" not in config:
      #  config["queries"] = {}
      #if "pageloadEvent" not in config["queries"]:
      #  config["queries"]["pageloadEvent"] = {}
      #config["queries"]["pageloadEvent"]["branch"] = branch
      #config["queries"]["pageloadEvent"]["date"] = date
      #config["queries"]["pageloadEvent"]["query"] = query
      return query


  def getEventData_Incremental(self, config, branch):
    dataFiles=[]
    currentDate=datetime.strptime(config['startDate'], "%Y-%m-%d")
    endDate=datetime.strptime(config['endDate'], "%Y-%m-%d")
    delta=timedelta(days=1)

    while currentDate <= endDate:
      currentDateString = currentDate.strftime("%Y-%m-%d")
      slug = config['slug']
      query = self.generateEventsQuery(config, "control", currentDateString)

      print("Running query: " + query)
      job = self.client.query(query)

      print(f"Writing results for {currentDateString} to disk.")
      filename=os.path.join(self.dataDir, f"{slug}-pageload-events-{branch}-{currentDateString}.pkl")
      df = job.to_dataframe()
      df.to_pickle(filename)

      dataFiles.append(filename)
      currentDate += delta
    return dataFiles

  def checkForExistingData(self, slug, branch, date=None):
    if date is None:
      filename=os.path.join(self.dataDir, f"{slug}-pageload-events-{branch}.pkl")
    else:
      filename=os.path.join(self.dataDir, f"{slug}-pageload-events-{branch}-{date}.pkl")

    if self.skipCache:
      df = None
    else:
      try:
        df = pd.read_pickle(filename)
        print(f"Found local data in __{filename}__")
      except:
        df = None
    return df

  def getEventData_Full(self, config, branch):
    slug = config['slug']
    data = self.checkForExistingData(slug, branch)
    if data is not None:
      return data

    query = self.generateEventsQuery(config, branch)
      
    print("Running query: " + query)
    job = self.client.query(query)

    print(f"Writing __{slug}__ results for branch __{branch}__ to disk.")
    filename=os.path.join(self.dataDir, f"{slug}-pageload-events-{branch}.pkl")
    df = job.to_dataframe()
    df.to_pickle(filename)
    return df
