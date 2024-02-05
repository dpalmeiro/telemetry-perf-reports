from livestats import livestats
from scipy import stats
import numpy as np
import json
import sys

# Expand the histogram into an array of values
def expand_histogram(bins, counts):
  array = []
  for i in range(len(bins)):
    for j in range(1, int(counts[i]/2.0)):
      array.append(bins[i])
  return array

def calc_cohen_d(x1, x2, s1, s2, n1, n2):
  effect_size = (x1-x2)/np.sqrt(((n1-1)*s1**2 + (n2-1)*s2**2) / (n1+n2-2))
  return effect_size

def rank_biserial_correlation(n1, n2, U):
  return (1-2*U/(n1*n2))

# Calculate two-way t-test with unequal sample size and unequal variances.
# Return the t-value, p-value, and effect size via cohen's d.
def calc_t_test(x1, x2, s1, s2, n1, n2): 
    s_prime = np.sqrt((s1**2/n1) + (s2**2)/n2)
    t_value = (x1-x2)/s_prime

    df = (s1**2/n1 + s2**2/n2)**2/( (s1**2/n1)**2/(n1-1) + (s2**2/n2)**2/(n2-1) )
    p_value = 2 * (1-(stats.t.cdf(abs(t_value), df)))
    effect_size = calc_cohen_d(x1, x2, s1, s2, n1, n2)

    return [t_value, p_value, effect_size]

# Calculate Mann-Whitney U test when input datasets are histograms.
# TODO:  Actually implement this.
def calc_mwu_test(bins1, counts1, bins2, counts2):
  u_value = 0
  p_value = 0
  effect_size = 0
  return [u_value, p_value, effect_size]

# Calculate Chi squared test when input datasets are histograms.
# TODO:  Actually implement this.
def calc_chi_sq_test(bins1, counts1, bins2, counts2):
  chi_value = 0
  p_value = 0
  effect_size = 0
  return [chi_value, p_value, effect_size]

# Calculate Kolmogorov–Smirnov test when input datasets are histograms.
# TODO:  Actually implement this.
def calc_ks_test(bins1, counts1, bins2, counts2):
  ks_value = 0
  p_value = 0
  effect_size = 0
  return [ks_value, p_value, effect_size]

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
def calc_histogram_quantiles(bins, density):
  vals = []
  quantiles = []
  q = 0
  j = 0
  for i in range(len(bins)):
    q = q + density[i]
    vals.append(bins[i])
    quantiles.append(q)

  return [quantiles, vals]

def calc_histogram_density(counts, n):
  density = []
  cdf = []
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
  mean = float(mean)/float(n-1)

  var = 0
  for i in range(len(bins)):
    bucket = float(bins[i])
    count =  float(counts[i])
    var = var + count*(bucket-mean)**2
  var = var/(n-1)
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
  [quantiles, vals] = calc_histogram_quantiles(bins, density)
  data["quantiles"] = quantiles
  data["quantile_vals"] = vals

def calculate_histogram_tests(bins, counts, data, control):
  mean_control = control['mean']
  std_control = control['std']
  n_control = control['n']

  mean = data['mean']
  std = data['std']
  n = data['n']
  
  # Calculate t-test
  [t_value, p_value, effect] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
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
                  "quantiles": [],
                  "quantile_vals": []
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
                   "quantiles": [],
                   "quantile_vals": []
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
        [quantiles, vals] = calc_histogram_quantiles(bins, density)
        self.results[branch][segment]["histograms"][hist_name]["quantiles"] = quantiles
        self.results[branch][segment]["histograms"][hist_name]["quantile_vals"] = vals

        if branch != self.control:
          # Get mean, var, and n from results
          mean_control = self.results[self.control][segment]["histograms"][hist_name]['mean']
          std_control = self.results[self.control][segment]["histograms"][hist_name]['std']
          n_control = self.results[self.control][segment]["histograms"][hist_name]['n']
          # Calculate t-test
          [t_value, p_value, effect] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
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
        # Calculate quantiles
        [quantiles, vals] = calc_histogram_quantiles(bins, density)
        self.results[branch][segment]["pageload_event_metrics"][metric]["quantiles"] = quantiles
        self.results[branch][segment]["pageload_event_metrics"][metric]["quantile_vals"] = vals

        if branch != self.control:
          # Get mean, var, and n from results
          mean_control = self.results[self.control][segment]["pageload_event_metrics"][metric]['mean']
          std_control = self.results[self.control][segment]["pageload_event_metrics"][metric]['std']
          n_control = self.results[self.control][segment]["pageload_event_metrics"][metric]['n']
          # Calculate t-test
          [t_value, p_value, effect] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
          self.results[branch][segment]["pageload_event_metrics"][metric]["t-test"] = {}
          self.results[branch][segment]["pageload_event_metrics"][metric]["t-test"]["score"] = t_value
          self.results[branch][segment]["pageload_event_metrics"][metric]["t-test"]["p-value"] = p_value
