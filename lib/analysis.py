from livestats import livestats
from scipy import stats
import numpy as np
import json

def calc_confidence_interval(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m, se = np.mean(a), stats.sem(a)
    h = se * stats.t.ppf((1 + confidence) / 2., n-1)
    return [m, se, m-h, m+h]

class FullDataAnalyzer:
  def __init__(self, config):
    self.controldf = None
    self.config = config

    self.binVals = {}
    for field in self.config["pageload_event_fields"]:
      self.binVals[field] = 'auto'

  def createEmptyDataTemplate(self):
    data = {}
    for segment in self.config["segments"]:
      data[segment] = {}
  
    for segment in data:
      data[segment] = {}
      for field in self.config["pageload_event_fields"]:
        data[segment][field] = { "mean": 0,
                                 "confidence": {
                                    "min": 0,
                                    "max": 0
                                 },
                                 "se": 0,
                                 "var": 0,
                                 "std": 0,
                                 "pdf":
                                       {
                                        "values" : [],
                                        "density" : []
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

  def processPageLoadEventData(self, df, branch):
    print(f"Calculating statistics for branch: {branch}")
    data = self.createEmptyDataTemplate()
    for segment in data:
      print(f"  processing segment: {segment}")
      if segment == "All":
        subset = df
      else:
        # Some OS like Windows have multiple values (i.e. Windows 10, Windows 7, etc)
        subset = df[df["os"].str.contains(segment)==True]

      if self.controldf is not None:
        if segment == "All":
          control_subset = self.controldf
        else:
          # Some OS like Windows have multiple values (i.e. Windows 10, Windows 7, etc)
          control_subset = self.controldf[self.controldf["os"].str.contains(segment)==True]
  
      for field in self.config["pageload_event_fields"]:
        print(f"      processing metric: {field}")

        # Filter values to given min and max values.
        minval = self.config["pageload_event_fields"][field][0]
        maxval = self.config["pageload_event_fields"][field][1]
        field_data = subset[subset[field].between(minval, maxval)][field]
        if self.controldf is not None:
          control_field_data = control_subset[control_subset[field].between(minval, maxval)][field]

        # Calculate mean and confidence interval
        [mean, se, minrange, maxrange] = calc_confidence_interval(field_data)
        data[segment][field]['mean'] = mean
        data[segment][field]['se'] = se
        data[segment][field]['confidence']['max'] = maxrange
        data[segment][field]['confidence']['min'] = minrange
  
        # Calculate variance
        data[segment][field]['var'] = field_data.var()
  
        # Calculate std
        data[segment][field]['std'] = field_data.std()

        # Calculate student t-test
        if self.controldf is not None:
          t_score, p_value = stats.ttest_ind(control_field_data, field_data)
          data[segment][field]["t-test"] = {}
          data[segment][field]["t-test"]["score"] = t_score
          data[segment][field]["t-test"]["p-value"] = p_value

        # Calculate mann-whitney-u test
        #if self.controldf is not None:
        #  u_score, p_value = stats.mannwhitneyu(control_field_data, field_data, method="asymptotic")
        #  data[segment][field]["mwu-test"] = {}
        #  data[segment][field]["mwu-test"]["score"] = t_score
        #  data[segment][field]["mwu-test"]["p-value"] = p_value

        # Calculate histogram
        [density, vals] = np.histogram(field_data, bins=self.binVals[field], density=True)
        if type(self.binVals[field]) is str:
          self.binVals[field] = vals
        data[segment][field]["pdf"]["density"] = density.tolist()
        data[segment][field]["pdf"]["values"] = list(map(int,vals.tolist()))
  
        # Calculate quantiles
        for quantile in data[segment][field]["quantile"]:
          data[segment][field]["quantile"][quantile]= field_data.quantile(q=quantile)
  
    # Save the control df so we can calculate MWU-test and T-test
    if self.controldf is None:
      self.controldf = df.copy()
    return data
