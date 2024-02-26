import requests
import json
import yaml
import sys
import datetime

def checkForLocalFile(dataDir, filename):
  try:
    with open(filename, 'r') as f:
      data = json.load(f)
      return data
  except:
    return None

def annotateMetrics(dataDir, config, skipCache):
  annotateHistograms(dataDir, config, skipCache)
  annotatePageloadEventMetrics(dataDir, config, skipCache)

def annotatePageloadEventMetrics(dataDir, config, skipCache):
  event_schema = retrievePageloadEventSchema(dataDir, skipCache)

  event_metrics = config['pageload_event_metrics'].copy()
  config['pageload_event_metrics'] = {}

  for metric in event_metrics:
    config['pageload_event_metrics'][metric] = {}
    if metric in event_schema:
      config['pageload_event_metrics'][metric]["desc"] = event_schema[metric]["description"]
      config['pageload_event_metrics'][metric]["min"] = event_metrics[metric][0]
      config['pageload_event_metrics'][metric]["max"] = event_metrics[metric][1]
    else:
      print(f"ERROR: {metric} not found in pageload event schema.") 
      sys.exit(1)

def annotateHistograms(dataDir, config, skipCache):
  histogram_schema = retrieveHistogramsSchema(dataDir, skipCache)

  histograms = config['histograms'].copy()
  config['histograms'] = {}
  for i,hist in enumerate(histograms):
    config['histograms'][hist] = {}
    hist_name = hist.split('.')[-1].upper()
    if hist_name in histogram_schema:
      config['histograms'][hist]["desc"] = histogram_schema[hist_name]["description"]
      kind = histogram_schema[hist_name]["kind"]
      if kind=="categorical" or kind=="boolean":
        config['histograms'][hist]["kind"] = "categorical"
        if "labels" in histogram_schema[hist_name]:
          config['histograms'][hist]["labels"] = histogram_schema[hist_name]["labels"]
        else:
          config['histograms'][hist]["labels"] = []
          config['histograms'][hist]["labels"].append("no")
          config['histograms'][hist]["labels"].append("yes")
      else:
        config['histograms'][hist]["kind"] = "numerical"
    else:
      print(f"ERROR: {hist_name} not found in histograms schema.") 
      sys.exit(1)

def retrieveHistogramsSchema(dataDir, skipCache):
  filename=f"{dataDir}/histograms-schema.json"
  if skipCache:
    values = None
  else:
    values = checkForLocalFile(dataDir, filename)

  if values is not None:
    print(f"Using local histograms schema in {filename}")
    return values

  url=f'https://hg.mozilla.org/mozilla-central/raw-file/tip/toolkit/components/telemetry/Histograms.json'
  print(f"Loading Histograms schema from {url}")
  response = requests.get(url)
  if response.ok:
    values = response.json()
    with open(filename, 'w') as f:
      json.dump(values, f, indent=2)
    return values
  else:
    print(f"Failed to retrieve {url}: {response.status_code}")
    sys.exit(1)

def retrievePageloadEventSchema(dataDir, skipCache):
  filename=f"{dataDir}/pageload-event-schema.json"
  if skipCache:
    values = None
  else:
    values = checkForLocalFile(dataDir, filename)

  if values is not None:
    print(f"Using local pageload event schema in {filename}")
    return values

  url=f'https://hg.mozilla.org/mozilla-central/raw-file/tip/dom/metrics.yaml'
  print(f"Loading pageload event schema from {url}")
  response = requests.get(url)
  if response.ok:
    data = yaml.safe_load(response.text)
    values = data['perf']['page_load']['extra_keys']
    with open(filename, 'w') as f:
      json.dump(values, f, indent=2)
    return values
  else:
    print(f"Failed to retrieve {url}: {response.status_code}")
    sys.exit(1)

def retrieveNimbusAPI(dataDir, slug, skipCache):
  filename = f"{dataDir}/{slug}-nimbus-API.json"
  if skipCache:
    values = None
  else:
    values = checkForLocalFile(dataDir, filename)
  if values is not None:
    print(f"Using local config found in {filename}")
    return values

  url=f'https://experimenter.services.mozilla.com/api/v6/experiments/{slug}'
  print(f"Loading nimbus API from {url}")
  response = requests.get(url)
  if response.ok:
    values = response.json()
    with open(filename, 'w') as f:
        json.dump(values, f, indent=2)
    return values
  else:
    print(f"Failed to retrieve {url}: {response.status_code}")
    sys.exit(1)

# We only care about a few values from the API.
# Specifically, the branch slugs, channel and start/end dates.
def extractValuesFromAPI(api):
  values = {}
  values["startDate"] = api["enrollmentEndDate"]
  values["endDate"] = api["endDate"]
  values["channel"] = api["channel"]

  if values["endDate"] == None:
    now = datetime.datetime.now();
    values["endDate"] = now.strftime('%Y-%m-%d')

  values["branches"] = []
  for branch in api["branches"]:
    values["branches"].append(branch["slug"])
  return values

def parseNimbusAPI(dataDir, slug, skipCache):
  apiValues = retrieveNimbusAPI(dataDir, slug, skipCache)
  return extractValuesFromAPI(apiValues)

def parseConfigFile(configFile):
  with open(configFile, "r") as configData:
    config = json.load(configData)
    configData.close()

  if "branches" in config:
    config["is_experiment"] = False
  else:
    config["is_experiment"] = True

  return config
