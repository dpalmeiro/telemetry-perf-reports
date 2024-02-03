from livestats import livestats
from scipy import stats
import numpy as np
import json
import sys

def calc_t_test(x1, x2, s1, s2, n1, n2): 
    degrees_of_freedom = (s1**2/n1 + s2**2/n2)**2/( (s1**2/n1)**2/(n1-1) + (s2**2/n2)**2/(n2-1) )
    s_prime = np.sqrt((s1**2/n1) + (s2**2)/n2)
    t_value = (x1-x2)/s_prime
    p_value = 2 * (1-(stats.t.cdf(abs(t_value), degrees_of_freedom)))
    return [t_value, p_value]

def calc_cdf_from_density(density, vals):
  cdf = []
  sum = 0
  for i in range(0,len(density)-2):
    width = vals[i+1]-vals[i]
    cdf_val = sum+density[i]*width
    sum = cdf_val
    cdf.append(cdf_val)

  width = vals[-1]-vals[-2]
  cdf_val = sum+density[-1]*width
  sum = cdf_val
  cdf.append(cdf_val)
  return cdf

# TODO: Interpolate the quantiles.
def calc_histogram_quantiles(bins, density, quantiles):
  vals = []
  q = 0
  j = 0
  for i in range(len(bins)):
    q = q + density[i]
    if q >= quantiles[j]:
      vals.append(bins[i])
      j=j+1
      if j==len(quantiles)-1:
        break

  while len(vals) < len(quantiles):
    vals.append(bins[-1])
  return vals

def calc_histogram_density(counts, n):
  density = []
  cdf = [0]
  cum = 0
  for i in range(len(counts)):
    density.append(float(counts[i]/n))
    cum = cum+counts[i]
    cdf.append(float(cum))
  cdf = [x / cum for x in cdf]
  return [density, cdf]

def calc_histogram_mean_var(bins, counts):
  mean = 0
  n = 0
  for i in range(len(bins)):
    bucket = float(bins[i])
    count  = float(counts[i])
    n = n + count
    mean = mean + bucket*count
  mean = float(mean)/float(n)

  var = 0
  for i in range(len(bins)):
    bucket = float(bins[i])
    count =  float(counts[i])
    var = var + count*(bucket-mean)**2
  var = var/n
  std = np.sqrt(var)

  return [mean, var, std, n]

def calculate_histogram_stats(bins, counts, data):
  # Calculate mean, std, and var
  [mean, var, std, n] = calc_histogram_mean_var(bins, counts)
  data['mean'] = mean
  data['std'] = std
  data['var'] = var
  data['n'] = n

  # Calculate densities
  [density, cdf] = calc_histogram_density(counts, n)
  data["pdf"]["cdf"] = cdf
  data["pdf"]["density"] = density
  data["pdf"]["values"] = bins

  # Calculate quantiles
  quantiles = sorted(list(data["quantile"].keys()))
  vals = calc_histogram_quantiles(bins, density, quantiles)
  data["quantile"] = {}
  for i in range(len(quantiles)):
    data["quantile"][quantiles[i]] = vals[i]

def calculate_histogram_tests(bins, counts, data, control):
  mean_control = control['mean']
  std_control = control['std']
  n_control = control['n']

  mean = data['mean']
  std = data['std']
  n = data['n']
  
  # Calculate t-test
  [t_value, p_value] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
  data["t-test"] = {}
  data["t-test"]["score"] = t_value
  data["t-test"]["p-value"] = p_value

def calc_confidence_interval(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), stats.sem(a)
    h = se * stats.t.ppf((1 + confidence) / 2., n-1)
    return [m, se, m-h, m+h]

def createEmptyResultsTemplate(config):
  template = {}
  for branch in config['branches']:
    template[branch] = {}
    for segment in config['segments']:
      template[branch][segment] = {
                      "histograms": {},
                      "pageload_event_metrics": {}
                    }

      
      for histogram in config['histograms']:
        hist_name = histogram.split(".")[-1]
        template[branch][segment]["histograms"][hist_name] = {
                 "mean": 0,
                 "confidence": {
                    "min": 0,
                    "max": 0
                 },
                 "se": 0,
                 "var": 0,
                 "std": 0,
                 "n": 0,
                 "pdf":
                       {
                        "values" : [],
                        "density" : [],
                        "cdf": []
                       },
                 "quantile": 
                       {
                        0.1: 0, 
                        0.2: 0, 
                        0.3: 0, 
                        0.4: 0, 
                        0.5: 0,
                        0.6: 0,
                        0.7: 0,
                        0.8: 0,
                        0.9: 0,
                        0.95: 0,
                        0.99: 0,
                        1.0: 0
                       }
        }

        for metric in config["pageload_event_metrics"]:
          template[branch][segment]["pageload_event_metrics"][metric] = {
                   "mean": 0,
                   "confidence": {
                      "min": 0,
                      "max": 0
                   },
                   "se": 0,
                   "var": 0,
                   "std": 0,
                   "n": 0,
                   "pdf":
                         {
                          "values" : [],
                          "density" : [],
                          "cdf": []
                         },
                   "quantile": 
                         {
                          0.1: 0, 
                          0.2: 0, 
                          0.3: 0, 
                          0.4: 0, 
                          0.5: 0,
                          0.6: 0,
                          0.7: 0,
                          0.8: 0,
                          0.9: 0,
                          0.95: 0,
                          0.99: 0,
                          1.0: 0
                         }
          }
  return template

class DataAnalyzer:
  def __init__(self, config):
    self.config = config
    self.event_controldf = None
    self.control = self.config["branches"][0]
    self.results = createEmptyResultsTemplate(config)

    self.binVals = {}
    for field in self.config["pageload_event_metrics"]:
      self.binVals[field] = 'auto'

  def processTelemetryData(self, telemetryData):
    for branch in self.config['branches']:
      self.processTelemetryDataForBranch(telemetryData, branch)
    return self.results

  def processTelemetryDataForBranch(self, data, branch):
    self.processHistogramData(data, branch)
    self.processPageLoadEventData(data, branch)

  def processHistogramData(self, data, branch):
    print(f"Calculating histogram statistics for branch: {branch}")
    for segment in self.config['segments']:
      print(f"  processing segment: {segment}")
    
      for hist in self.config["histograms"]:
        hist_name = hist.split('.')[-1]
        print(f"      processing histogram: {hist}")

        bins = data[branch][segment]["histograms"][hist]["bins"]
        counts = data[branch][segment]["histograms"][hist]["counts"]

        # Calculate mean, std, and var
        [mean, var, std, n] = calc_histogram_mean_var(bins, counts)
        self.results[branch][segment]["histograms"][hist_name]['mean'] = mean
        self.results[branch][segment]["histograms"][hist_name]['std'] = std
        self.results[branch][segment]["histograms"][hist_name]['var'] = var
        self.results[branch][segment]["histograms"][hist_name]['n'] = n

        # Calculate densities
        [density, cdf] = calc_histogram_density(counts, n)
        self.results[branch][segment]["histograms"][hist_name]["pdf"]["cdf"] = cdf
        self.results[branch][segment]["histograms"][hist_name]["pdf"]["density"] = density
        self.results[branch][segment]["histograms"][hist_name]["pdf"]["values"] = bins

        # Calculate quantiles
        quantiles = sorted(list(self.results[branch][segment]["histograms"][hist_name]["quantile"].keys()))
        vals = calc_histogram_quantiles(bins, density, quantiles)
        self.results[branch][segment]["histograms"][hist_name]["quantile"] = {}
        for i in range(len(quantiles)):
          self.results[branch][segment]["histograms"][hist_name]["quantile"][quantiles[i]] = vals[i]

        if branch != self.control:
          # Get mean, var, and n from results
          mean_control = self.results[self.control][segment]["histograms"][hist_name]['mean']
          std_control = self.results[self.control][segment]["histograms"][hist_name]['std']
          n_control = self.results[self.control][segment]["histograms"][hist_name]['n']
          # Calculate t-test
          [t_value, p_value] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
          self.results[branch][segment]["histograms"][hist_name]["t-test"] = {}
          self.results[branch][segment]["histograms"][hist_name]["t-test"]["score"] = t_value
          self.results[branch][segment]["histograms"][hist_name]["t-test"]["p-value"] = p_value

  def processPageLoadEventData(self, data, branch):
    print(f"Calculating pageload event statistics for branch: {branch}")
    for segment in self.config['segments']:
      print(f"  processing segment: {segment}")
    
      for metric in self.config["pageload_event_metrics"]:
        print(f"      processing metric: {metric}")

        bins = data[branch][segment]["pageload_event_metrics"][metric]["bins"]
        counts = data[branch][segment]["pageload_event_metrics"][metric]["counts"]

        # Calculate mean, std, and var
        [mean, var, std, n] = calc_histogram_mean_var(bins, counts)
        self.results[branch][segment]["pageload_event_metrics"][metric]['mean'] = mean
        self.results[branch][segment]["pageload_event_metrics"][metric]['std'] = std
        self.results[branch][segment]["pageload_event_metrics"][metric]['var'] = var
        self.results[branch][segment]["pageload_event_metrics"][metric]['n'] = n

        # Calculate densities
        [density, cdf] = calc_histogram_density(counts, n)
        self.results[branch][segment]["pageload_event_metrics"][metric]["pdf"]["cdf"] = cdf
        self.results[branch][segment]["pageload_event_metrics"][metric]["pdf"]["density"] = density
        self.results[branch][segment]["pageload_event_metrics"][metric]["pdf"]["values"] = bins

        # Calculate quantiles
        quantiles = sorted(list(self.results[branch][segment]["pageload_event_metrics"][metric]["quantile"].keys()))
        vals = calc_histogram_quantiles(bins, density, quantiles)
        self.results[branch][segment]["pageload_event_metrics"][metric]["quantile"] = {}
        for i in range(len(quantiles)):
          self.results[branch][segment]["pageload_event_metrics"][metric]["quantile"][quantiles[i]] = vals[i]

        if branch != self.control:
          # Get mean, var, and n from results
          mean_control = self.results[self.control][segment]["pageload_event_metrics"][metric]['mean']
          std_control = self.results[self.control][segment]["pageload_event_metrics"][metric]['std']
          n_control = self.results[self.control][segment]["pageload_event_metrics"][metric]['n']
          # Calculate t-test
          [t_value, p_value] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
          self.results[branch][segment]["pageload_event_metrics"][metric]["t-test"] = {}
          self.results[branch][segment]["pageload_event_metrics"][metric]["t-test"]["score"] = t_value
          self.results[branch][segment]["pageload_event_metrics"][metric]["t-test"]["p-value"] = p_value
