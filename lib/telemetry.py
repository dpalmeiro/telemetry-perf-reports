import os
import numpy as np
import pandas as pd
from google.cloud import bigquery
from django.template import Template, Context
from django.template.loader import get_template


def segments_are_all_OS(segments):
  os_segments = set(["Windows", "All", "Linux", "Mac"])
  for segment in segments:
    if segment not in os_segments:
      return False
  return True

class TelemetryClient:
  def __init__(self, dataDir, config, skipCache):
    self.client = bigquery.Client()
    self.config = config
    self.dataDir = dataDir
    self.skipCache = skipCache

  def collectResultsFromQuery_OS_segments(self, results, branch, segment, df_events, histograms):
    for histogram in self.config['histograms']:
      df = histograms[histogram]
      if segment == "All":
        subset = df[df["branch"] == branch][['bucket', 'counts']].groupby(['bucket']).sum()
        buckets = list(subset.index)
        counts = list(subset['counts'])
      else:
        subset = df[(df["segment"] == segment) & (df["branch"] == branch)]
        buckets = list(subset['bucket'])
        counts = list(subset['counts'])

      assert len(buckets) == len(counts)
      results[branch][segment]['histograms'][histogram] = {}
      results[branch][segment]['histograms'][histogram]['bins'] = buckets
      results[branch][segment]['histograms'][histogram]['counts'] = counts
      print(f"    len({histogram}) = ", len(buckets))

    for metric in self.config['pageload_event_metrics']:
      minval = self.config["pageload_event_metrics"][metric][0]
      maxval = self.config["pageload_event_metrics"][metric][1]

      if segment == "All":
        subset = df_events[(df_events["branch"] == branch) & 
          df_events['bucket'].between(minval, maxval)][['bucket', f"{metric}_counts"]].groupby(['bucket']).sum()
        buckets = list(subset.index)
        counts = list(subset[f"{metric}_counts"])
      else:
        subset = df_events[(df_events["segment"] == segment) & 
                           (df_events["branch"] == branch) & 
                            df_events['bucket'].between(minval, maxval)]
        buckets = list(subset["bucket"])
        counts = list(subset[f"{metric}_counts"])
      assert len(buckets) == len(counts)

      results[branch][segment]['pageload_event_metrics'][metric] = {}
      results[branch][segment]['pageload_event_metrics'][metric]['bins'] = buckets
      results[branch][segment]['pageload_event_metrics'][metric]['counts'] = counts
      print(f"    len(pageload event: {metric}) = ", len(buckets))


  def getResults(self):
    # Get data for each pageload event metrics.
    df_events = self.getPageloadEventData()
    print(df_events)

    #Get data for each histogram in this segment.
    histograms = {}
    for histogram in self.config['histograms']:
      histograms[histogram] = self.getHistogramData(self.config, histogram)
      print(histograms[histogram])

    # Combine histogram and pageload event results.
    results = {}
    for branch in self.config['branches']:
      results[branch] = {}
      for segment in self.config['segments']:
        print (f"Aggregating results for segment={segment} and branch={branch}")
        results[branch][segment] = {"histograms": {}, "pageload_event_metrics": {}}

        # Special case when segments is OS only.
        self.collectResultsFromQuery_OS_segments(results, branch, segment, df_events, histograms)
    return results

  def generatePageloadEventQuery_OS_segments(self):
    t = get_template("events_os_segments.sql")

    maxBucket = 0
    minBucket = 30000
    for metric in self.config['pageload_event_metrics']:
      metricMin = self.config['pageload_event_metrics'][metric][0]
      metricMax = self.config['pageload_event_metrics'][metric][1]
      if metricMax > maxBucket:
        maxBucket = metricMax
      if metricMin < minBucket:
        minBucket = metricMin

    context = {
        "minBucket": minBucket,
        "maxBucket": maxBucket,
        "is_experiment": self.config['is_experiment'],
        "slug": self.config['slug'],
        "channel": self.config['channel'],
        "startDate": self.config['startDate'],
        "endDate": self.config['endDate'],
        "metrics": self.config['pageload_event_metrics'],
    }
    query = t.render(context)
    # Remove empty lines before returning
    query = "".join([s for s in query.strip().splitlines(True) if s.strip()])
    return query

  def generatePageloadEventQuery_Generic(self):
    t = get_template("events_generic.sql")

    segmentInfo = []
    for segment in self.config['segments']:
      segmentInfo.append({
            "name": segment, 
            "conditions": self.config['segments'][segment]
            })

    maxBucket = 0
    minBucket = 30000
    for metric in self.config['pageload_event_metrics']:
      metricMin = self.config['pageload_event_metrics'][metric][0]
      metricMax = self.config['pageload_event_metrics'][metric][1]
      if metricMax > maxBucket:
        maxBucket = metricMax
      if metricMin < minBucket:
        minBucket = metricMin

    context = {
        "minBucket": minBucket,
        "maxBucket": maxBucket,
        "is_experiment": self.config['is_experiment'],
        "slug": self.config['slug'],
        "channel": self.config['channel'],
        "startDate": self.config['startDate'],
        "endDate": self.config['endDate'],
        "metrics": self.config['pageload_event_metrics'],
        "segments": segmentInfo
    }
    query = t.render(context)
    # Remove empty lines before returning
    query = "".join([s for s in query.strip().splitlines(True) if s.strip()])
    return query

  # Use this query if the segments is OS only which is much faster than generic query.
  def generateHistogramQuery_OS_segments(self, histogram):
    t = get_template("histogram_os_segments.sql")

    context = {
        "is_experiment": self.config['is_experiment'],
        "slug": self.config['slug'],
        "channel": self.config['channel'],
        "startDate": self.config['startDate'],
        "endDate": self.config['endDate'],
        "histogram": histogram,
    }
    query = t.render(context)
    # Remove empty lines before returning
    query = "".join([s for s in query.strip().splitlines(True) if s.strip()])
    return query

  def generateHistogramQuery_Generic(self, histogram):
    t = get_template("histogram_generic.sql")

    segmentInfo = []
    for segment in self.config['segments']:
      segmentInfo.append({
            "name": segment, 
            "conditions": self.config['segments'][segment]
            })

    context = {
        "is_experiment": self.config['is_experiment'],
        "slug": self.config['slug'],
        "channel": self.config['channel'],
        "startDate": self.config['startDate'],
        "endDate": self.config['endDate'],
        "histogram": histogram,
        "segments": segmentInfo
    }
    query = t.render(context)
    # Remove empty lines before returning
    query = "".join([s for s in query.strip().splitlines(True) if s.strip()])
    return query

  def checkForExistingData(self, filename):
    if self.skipCache:
      df = None
    else:
      try:
        df = pd.read_pickle(filename)
        print(f"Found local data in {filename}")
      except:
        df = None
    return df

  def getHistogramData(self, config, histogram):
    slug = config['slug']
    hist_name = histogram.split('.')[-1]
    filename=os.path.join(self.dataDir, f"{slug}-{hist_name}.pkl")

    df = self.checkForExistingData(filename)
    if df is not None:
      return df

    if segments_are_all_OS(self.config['segments']):
      query = self.generateHistogramQuery_OS_segments(histogram)
    else:
      query = self.generateHistogramQuery_Generic(histogram)

    print("Running query:\n" + query)
    job = self.client.query(query)
    df = job.to_dataframe()
    print(f"Writing '{slug}' histogram results for {histogram} to disk.")
    df.to_pickle(filename)
    return df

  def getPageloadEventData(self):
    slug = self.config['slug']
    filename=os.path.join(self.dataDir, f"{slug}-pageload-events.pkl")

    df = self.checkForExistingData(filename)
    if df is not None:
      return df

    if segments_are_all_OS(self.config['segments']):
      query = self.generatePageloadEventQuery_OS_segments()
    else:
      query = self.generatePageloadEventQuery_Generic()

    print("Running query:\n" + query)
    job = self.client.query(query)
    df = job.to_dataframe()
    print(f"Writing '{slug}' pageload event results to disk.")
    df.to_pickle(filename)
    return df
