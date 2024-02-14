import json
import os
import numpy as np
from scipy import interpolate
from django.template import Template, Context
from django.template.loader import get_template
from airium import Airium
from bs4 import BeautifulSoup as bs

# These values are mostly hand-wavy that seem to 
# fit the telemetry result impacts.
def get_cohen_effect_meaning(d):
  d_abs = abs(d)
  if d_abs <= 0.05:
    return "Small"
  if d_abs <= 0.1:
    return "Medium"
  else:
    return "Large"

# CubicSpline requires a monotonically increasing x.
# Remove duplicates.
def cubic_spline_prep(x, y):
  new_x = []
  new_y = []
  for i in range(1, len(x)):
    if x[i]-x[i-1] > 0:
      new_x.append(x[i])
      new_y.append(y[i])
  return [new_x, new_y]

def cubic_spline_smooth(x, y, x_new):
  [x_prep, y_prep] = cubic_spline_prep(x, y)
  tck = interpolate.splrep(x_prep, y_prep, k=3)
  y_new = interpolate.splev(x_new, tck, der=0)
  return list(y_new)

def find_value_at_quantile(values, cdf, q=0.95):
  for i, e in reversed(list(enumerate(cdf))):
    if cdf[i] <= q:
      if i==len(cdf)-1:
        return values[i]
      else:
        return values[i+1]

def getIconForSegment(segment):
  iconMap = {
      "All": "fa-solid fa-globe",
      "Windows": "fa-brands fa-windows",
      "Linux": "fa-brands fa-linux",
      "Mac": "fa-brands fa-apple"
  }
  if segment in iconMap:
    return iconMap[segment]
  else:
    return "fa-solid fa-chart-simple"

class ReportGenerator:
  def __init__(self, data):
    self.data = data
    self.doc = Airium()

  def createHeader(self):
    t = get_template("header.html")
    context = {
          "title": f"{self.data['slug']} experimental results"
    }
    self.doc(t.render(context))

  def endDocument(self):
    self.doc("</body>")
    return

  def createSidebar(self):
    t = get_template("sidebar.html")

    segments = []
    for segment in self.data['segments']:
      entry = { "name": segment,
                "icon": getIconForSegment(segment),
                "pageload_metrics" : [],
                "histograms" : []
              }
      for metric in self.data['pageload_event_metrics']:
        entry["pageload_metrics"].append(metric)

      for histogram in self.data['histograms']:
        hist_name = histogram.split('.')[-1]
        entry["histograms"].append(hist_name)

      segments.append(entry)

    ctx = {
        "segments": segments
    }
    self.doc(t.render(ctx))

  def createSummarySection(self):
    t = get_template("summary.html")
    control=self.data["branches"][0]

    segments = []
    for segment in self.data["segments"]:
      metrics = []
      for metric_type in ["histograms", "pageload_event_metrics"]:
        for metric in self.data[metric_type]:
          if metric_type == "pageload_event_metrics":
            metric_name = f"pageload event: {metric}"
          else:
            metric = metric.split(".")[-1]
            metric_name = metric

          datasets = []
          for branch in self.data["branches"]:
            if branch == control:
              continue

            mean = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["mean"])
            std  = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["std"])

            branch_mean = self.data[branch][segment][metric_type][metric]["mean"]
            control_mean = self.data[control][segment][metric_type][metric]["mean"]
            uplift = (branch_mean-control_mean)/control_mean*100.0
            uplift_str = "{0:.1f}".format(uplift)

            pval = self.data[branch][segment][metric_type][metric]["tests"]["ttest"]["p-value"]
            effect_size = self.data[branch][segment][metric_type][metric]["tests"]["ttest"]["effect"]
            effect_meaning = get_cohen_effect_meaning(effect_size)
            effect_size = "{0:.2f}".format(effect_size)
            effect = f"{effect_meaning} (d={effect_size})"
        
            if pval >= 0.001:
              pval = "{0:.2f}".format(pval)
              effect = f"None (p={pval})"
              effect_meaning = "None"

            if effect_meaning == "None" or effect_meaning == "Small":
              style="font-weight: normal"
            else:
              if uplift >= 1.5:
                style="font-weight: bold; color: red"
              elif uplift <= -1.5:
                style="font-weight: bold; color: green"
              else:
                style="font-weight: normal"


            dataset = {
                "branch": branch,
                "mean": mean,
                "uplift": uplift_str,
                "std": std,
                "effect": effect,
                "style": style,
                "last": False
            }
            datasets.append(dataset);

          datasets[-1]["last"] = True
          metrics.append({ "desc": metric_name, 
                           "name": metric,
                           "datasets": datasets, 
                           "rowspan": len(datasets)})
      segments.append({"name": segment, "metrics": metrics}) 

    slug = self.data['slug']
    is_experiment = self.data['is_experiment']

    if is_experiment:
      startDate = self.data['startDate']
      endDate = self.data['endDate']
      channel = self.data['channel']
    else:
      startDate = None,
      endDate = None
      channel = None

    branches=[]
    for i in range(len(self.data['input']['branches'])):
      if is_experiment:
        branchInfo = {
            "name": self.data['input']['branches'][i]
        }
      else:
        branchInfo = {
            "name": self.data['input']['branches'][i]['name'],
            "startDate": self.data['input']['branches'][i]['startDate'],
            "endDate": self.data['input']['branches'][i]['endDate'],
            "channel": self.data['input']['branches'][i]['channel']
            
        }
      branches.append(branchInfo)

    context = { 
      "slug": slug,
      "is_experiment": is_experiment,
      "startDate": startDate,
      "endDate": endDate,
      "channel": channel,
      "branches": branches,
      "segments": segments,
      "branchlen": len(branches)
    }
    self.doc(t.render(context))

  def createConfigSection(self):
    t = get_template("config.html")
    context = { 
                "config": json.dumps(self.data["input"], indent=4),
                "queries": self.data['queries']
              }
    self.doc(t.render(context))

  def createCDFComparison(self, segment, metric, metric_type):
    t = get_template("cdf.html")

    control = self.data["branches"][0]
    values_control = self.data[control][segment][metric_type][metric]["pdf"]["values"]
    cdf_control = self.data[control][segment][metric_type][metric]["pdf"]["cdf"]

    maxValue = find_value_at_quantile(values_control, cdf_control)
    values_int = list(np.around(np.linspace(0, maxValue, 100), 2))

    datasets = []
    for branch in self.data["branches"]:
      values = self.data[branch][segment][metric_type][metric]["pdf"]["values"]
      density = self.data[branch][segment][metric_type][metric]["pdf"]["density"]
      cdf = self.data[branch][segment][metric_type][metric]["pdf"]["cdf"]

      # Smooth out pdf and cdf, and use common X values for each branch.
      density_int = cubic_spline_smooth(values, density, values_int)
      cdf_int = cubic_spline_smooth(values, cdf, values_int)

      dataset = {
          "branch": branch,
          "cdf": cdf_int,
          "density": density_int,
      }

      datasets.append(dataset)

    context = {
        "segment": segment,
        "metric": metric,
        "values": values_int,
        "datasets": datasets
    }
    self.doc(t.render(context))
    return

  def calculate_uplift_interp(self, quantiles, branch, segment, metric_type, metric):
    control = self.data["branches"][0]

    quantiles_control = self.data[control][segment][metric_type][metric]["quantiles"]
    values_control = self.data[control][segment][metric_type][metric]["quantile_vals"]
    [quantiles_control_n, values_control_n] = cubic_spline_prep(quantiles_control, values_control)
    tck = interpolate.splrep(quantiles_control_n, values_control_n, k=1)
    values_control_n = interpolate.splev(quantiles, tck, der=0)

    quantiles_branch = self.data[branch][segment][metric_type][metric]["quantiles"]
    values_branch = self.data[branch][segment][metric_type][metric]["quantile_vals"]
    [quantiles_branch_n, values_branch_n] = cubic_spline_prep(quantiles_branch, values_branch)
    tck = interpolate.splrep(quantiles_branch_n, values_branch_n, k=1)
    values_branch_n = interpolate.splev(quantiles, tck, der=0)

    uplifts = []
    diffs = []
    for i in range(len(quantiles)):
      diff = values_branch_n[i] - values_control_n[i]
      uplift = diff/values_control_n[i]*100
      diffs.append(diff)
      uplifts.append(uplift)

    return [diffs, uplifts]

  def createUpliftComparison(self, segment, metric, metric_type):
    t = get_template("uplift.html")

    control = self.data["branches"][0]
    quantiles = list(np.around(np.linspace(0.1, 0.90, 89), 2))

    datasets = []
    for branch in self.data["branches"]:
      if branch == control:
        continue

      [diff, uplift] = self.calculate_uplift_interp(quantiles, branch, segment, metric_type, metric)
      dataset = {
          "branch": branch,
          "diff": diff,
          "uplift": uplift,
      }
      datasets.append(dataset)

    maxVal = 0
    for x in diff:
      if abs(x) > maxVal:
        maxVal = abs(x)

    maxPerc = 0
    for x in uplift:
      if abs(x) > maxPerc:
        maxPerc = abs(x)

    context = {
        "segment": segment,
        "metric": metric,
        "quantiles": quantiles,
        "datasets": datasets,
        "upliftMax": maxPerc,
        "upliftMin": -maxPerc,
        "diffMax": maxVal,
        "diffMin": -maxVal
    }
    self.doc(t.render(context))

  def createMeanComparison(self, segment, metric, metric_type):
    t = get_template("mean.html")

    datasets = []
    control=self.data["branches"][0]
      
    for branch in self.data["branches"]:
      n = int(self.data[branch][segment][metric_type][metric]["n"])
      n = f'{n:,}'
      mean = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["mean"])

      if branch != control:
        branch_mean = self.data[branch][segment][metric_type][metric]["mean"]
        control_mean = self.data[control][segment][metric_type][metric]["mean"]
        uplift = (branch_mean-control_mean)/control_mean*100.0
        uplift = "{0:.1f}".format(uplift)
      else:
        uplift = ""

      se   = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["se"])
      std  = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["std"])

      dataset = {
          "branch": branch,
          "mean": mean,
          "uplift": uplift,
          "n": n,
          "se": se,
          "std": std,
          "control": branch==control
      }
      
      if branch != control:
        for test in self.data[branch][segment][metric_type][metric]["tests"]:
          effect = "{0:.2f}".format(self.data[branch][segment][metric_type][metric]["tests"][test]["effect"])
          pval = "{0:.2g}".format(self.data[branch][segment][metric_type][metric]["tests"][test]["p-value"])
          dataset[test] = {
              "effect": effect,
              "pval": pval
          }

      datasets.append(dataset)

    context = {
        "segment": segment,
        "metric": metric,
        "branches": self.data["branches"],
        "datasets": datasets
    }
    self.doc(t.render(context))

  def createMetrics(self, segment, metric, metric_type):
    # Add mean comparison
    self.createMeanComparison(segment, metric, metric_type)
    # Add PDF and CDF comparison
    self.createCDFComparison(segment, metric, metric_type)
    # Add uplift comparison
    self.createUpliftComparison(segment, metric, metric_type)

  def createPageloadEventMetrics(self, segment):
    for metric in self.data['pageload_event_metrics']:
      with self.doc.div(id=f"{segment}-{metric}", klass="cell"):
        # Add title for metric
        with self.doc.div(klass="title"):
          self.doc(f"({segment}) - {metric}")
        self.createMetrics(segment, metric, "pageload_event_metrics")

  def createHistogramMetrics(self, segment):
    for hist in self.data['histograms']:
      metric = hist.split('.')[-1]
      with self.doc.div(id=f"{segment}-{metric}", klass="cell"):
        # Add title for metric
        with self.doc.div(klass="title"):
          self.doc(f"({segment}) - {metric}")
        self.createMetrics(segment, metric, "histograms")
    return

  def createHTMLReport(self):
    self.createHeader()
    self.createSidebar()

    # Create a summary of results
    self.createSummarySection()

    # Generate charts and tables for each segment and metric
    for segment in self.data['segments']:
      self.createHistogramMetrics(segment)
      self.createPageloadEventMetrics(segment)

    # Dump the config and queries used for the report
    self.createConfigSection()

    self.endDocument()
    
    # Prettify the output
    soup = bs(str(self.doc), 'html.parser')
    return soup.prettify()
