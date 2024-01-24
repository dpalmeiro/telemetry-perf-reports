import urllib.request
import json
import sys

def checkForLocalAPI(dataDir, slug):
  try:
    with open(f"{dataDir}/{slug}-nimbus-API.json", 'r') as f:
      data = json.load(f)
      return data
  except:
    return None

def retrieveAPI(dataDir, slug, skipCache):
  if skipCache:
    values = None
  else:
    values = checkForLocalAPI(dataDir, slug)
  if values is not None:
    print(f"Using local config found in {slug}-nimbus-API.json")
    return values

  url=f'https://experimenter.services.mozilla.com/api/v6/experiments/{slug}'
  print(f"Loading nimbus API from {url}")
  try:
    with urllib.request.urlopen(url) as experimentAPIFile:
      values = json.load(experimentAPIFile)
      with open(f"{dataDir}/{slug}-nimbus-API.json", 'w') as f:
        json.dump(values, f, indent=2)
      return values
  except urllib.error.URLError as e:
    print(f"Failed to retrieve {url}: {e.reason}")
    sys.exit(1)

# We only care about a few values from the API.
# Specifically, the branch slugs, channel and start/end dates.
def extractValuesFromAPI(api):
  values = {}
  values["startDate"] = api["startDate"]
  values["enrollmentEndDate"] = api["enrollmentEndDate"]
  values["endDate"] = api["endDate"]
  values["channel"] = api["channel"]

  values["branches"] = []
  for branch in api["branches"]:
    values["branches"].append(branch["slug"])
  return values

def parseNimbusAPI(dataDir, slug, skipCache):
  apiValues = retrieveAPI(dataDir, slug, skipCache)
  return extractValuesFromAPI(apiValues)

def parseConfigFile(configFile):
  with open(configFile, "r") as configData:
    config = json.load(configData)
    configData.close()
  return config
