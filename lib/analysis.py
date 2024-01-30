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

def calc_histogram_stats(bins, counts):
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

def calc_confidence_interval(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), stats.sem(a)
    h = se * stats.t.ppf((1 + confidence) / 2., n-1)
    return [m, se, m-h, m+h]

class FullDataAnalyzer:
  def __init__(self, config, results):
    self.config = config
    self.event_controldf = None
    self.control = self.config["branches"][0]
    self.results = results

    self.binVals = {}
    for field in self.config["pageload_event_metrics"]:
      self.binVals[field] = 200

  def createEmptyDataTemplate(self):
    data = {}
    template = { "mean": 0,
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
                        "cdf:" : []
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
  
    for segment in self.config["segments"]:
      data[segment] = {
                        "histograms": {}, 
                        "pageload_event_metrics": {}
                      }
      for field in self.config["pageload_event_metrics"]:
        data[segment]["pageload_event_metrics"][field] = { 
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


      for hist in self.config["histograms"]:
        hist_name = hist.split(".")[-1]
        data[segment]["histograms"][hist_name] = {
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

    return data

  def processTelemetryData(self, df_hist, df_events, branch):
    data = self.createEmptyDataTemplate()

    # Process histogram data
    self.processHistogramData(df_hist, branch, data)
    # Process event data
    self.processPageLoadEventData(df_events, branch, data)

    return data

  def processHistogramData(self, df, branch, data):
    print(f"Calculating histogram statistics for branch: {branch}")
    for segment in data:
      print(f"  processing segment: {segment}")
      if segment == "All":
        subset = df
      else:
        # Some OS like Windows have multiple values (i.e. Windows 10, Windows 7, etc)
        subset = df[df["os"].str.contains(segment)==True]
    
      for hist in self.config["histograms"]:
        hist_name = hist.split('.')[-1]
        print(f"      processing histogram: {hist}")

        # Generate an aggregate histogram from each row
        subset_hist = {}
        for i in subset.index:
          if subset[hist_name][i] is None:
            continue
          j = json.loads(subset[hist_name][i])
          for bucket, value in j["values"].items():
            bucket = int(bucket)
            value  = int(value)
            if bucket in subset_hist:
              subset_hist[bucket] = subset_hist[bucket] + value
            else:
              subset_hist[bucket] = value

        # Separate the histogram into a list for bins and counts
        bins=[]
        counts=[]
        for [key,val] in sorted(subset_hist.items()):
          bins.append(key)
          counts.append(val)

        # Calculate mean, std, and var
        [mean, var, std, n] = calc_histogram_stats(bins, counts)
        data[segment]["histograms"][hist_name]['mean'] = mean
        data[segment]["histograms"][hist_name]['std'] = std
        data[segment]["histograms"][hist_name]['var'] = var
        data[segment]["histograms"][hist_name]['n'] = n

        # Calculate densities
        [density, cdf] = calc_histogram_density(counts, n)
        data[segment]["histograms"][hist_name]["pdf"]["cdf"] = cdf
        data[segment]["histograms"][hist_name]["pdf"]["density"] = density
        data[segment]["histograms"][hist_name]["pdf"]["values"] = bins

        # Calculate quantiles
        quantiles = sorted(list(data[segment]["histograms"][hist_name]["quantile"].keys()))
        vals = calc_histogram_quantiles(bins, density, quantiles)
        data[segment]["histograms"][hist_name]["quantile"] = {}
        for i in range(len(quantiles)):
          data[segment]["histograms"][hist_name]["quantile"][quantiles[i]] = vals[i]

        if branch != self.control:
          # Get mean, var, and n from results
          mean_control = self.results[self.control][segment]["histograms"][hist_name]['mean']
          std_control = self.results[self.control][segment]["histograms"][hist_name]['std']
          n_control = self.results[self.control][segment]["histograms"][hist_name]['n']
          # Calculate t-test
          [t_value, p_value] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
          data[segment]["histograms"][hist_name]["t-test"] = {}
          data[segment]["histograms"][hist_name]["t-test"]["score"] = t_value
          data[segment]["histograms"][hist_name]["t-test"]["p-value"] = p_value

    return data

  def processPageLoadEventData(self, df, branch, data):
    print(f"Calculating event statistics for branch: {branch}")
    for segment in data:
      print(f"  processing segment: {segment}")
      if segment == "All":
        subset = df
      else:
        # Some OS like Windows have multiple values (i.e. Windows 10, Windows 7, etc)
        subset = df[df["os"].str.contains(segment)==True]

      for field in self.config["pageload_event_metrics"]:
        print(f"      processing metric: {field}")

        # Filter values to given min and max values.
        minval = self.config["pageload_event_metrics"][field][0]
        maxval = self.config["pageload_event_metrics"][field][1]
        field_data = subset[subset[field].between(minval, maxval)][field]

        # Calculate mean and confidence interval
        [mean, se, minrange, maxrange] = calc_confidence_interval(field_data)
        data[segment]["pageload_event_metrics"][field]['mean'] = mean
        data[segment]["pageload_event_metrics"][field]['se'] = se
        data[segment]["pageload_event_metrics"][field]['confidence']['max'] = maxrange
        data[segment]["pageload_event_metrics"][field]['confidence']['min'] = minrange
  
        # Calculate variance
        var = field_data.var()
        data[segment]["pageload_event_metrics"][field]['var'] = var
  
        # Calculate std
        std = field_data.std()
        data[segment]["pageload_event_metrics"][field]['std'] = std

        # Save sample size
        n = len(field_data)
        data[segment]["pageload_event_metrics"][field]['n'] = n

        if branch != self.control:
          # Get mean, var, and n from results
          mean_control = self.results[self.control][segment]["pageload_event_metrics"][field]['mean']
          std_control = self.results[self.control][segment]["pageload_event_metrics"][field]['std']
          n_control = self.results[self.control][segment]["pageload_event_metrics"][field]['n']
          # Calculate t-test
          [t_value, p_value] = calc_t_test(mean, mean_control, std, std_control, n, n_control)
          data[segment]["pageload_event_metrics"][field]["t-test"] = {}
          data[segment]["pageload_event_metrics"][field]["t-test"]["score"] = t_value
          data[segment]["pageload_event_metrics"][field]["t-test"]["p-value"] = p_value

        # Calculate density
        [density, vals] = np.histogram(field_data, bins=self.binVals[field], density=True)
        cdf = calc_cdf_from_density(density, vals)
        if type(self.binVals[field]) is not list:
          self.binVals[field] = vals
        data[segment]["pageload_event_metrics"][field]["pdf"]["cdf"] = cdf
        data[segment]["pageload_event_metrics"][field]["pdf"]["density"] = density.tolist()
        data[segment]["pageload_event_metrics"][field]["pdf"]["values"] = list(map(int,vals.tolist()))
  
        # Calculate quantiles
        for quantile in data[segment]["pageload_event_metrics"][field]["quantile"]:
          data[segment]["pageload_event_metrics"][field]["quantile"][quantile]= field_data.quantile(q=quantile)
  
    return data
