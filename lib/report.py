import json
import os
import numpy as np
from scipy import interpolate
from django.template import Template, Context
from django.template.loader import get_template
from airium import Airium

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

  def createConfig(self):
    t = get_template("config.html")
    context = { "config": json.dumps(self.data["input"], indent=4) }
    self.doc(t.render(context))

  def createCDFComparison(self, segment, metric, metric_type):
    t = get_template("cdf.html")

    datasets = []
    control = self.data["branches"][0]
    for branch in self.data["branches"]:
      values = self.data[branch][segment][metric_type][metric]["pdf"]["values"]
      density = self.data[branch][segment][metric_type][metric]["pdf"]["density"]
      cdf = self.data[branch][segment][metric_type][metric]["pdf"]["cdf"]

      # Reduce the arrays to about 100 values so the report doesn't take forever.
      if len(cdf) > 100:
        n = int(len(cdf)/100)
      else:
        n = 1
      cdf_reduced = cdf[0::n]
      values_reduced = values[0::n]
      density_reduced = density[0::n]

      dataset = {
          "branch": branch,
          "cdf": cdf_reduced,
          "density": density_reduced
      }

      datasets.append(dataset)

    context = {
        "segment": segment,
        "metric": metric,
        "values": values_reduced,
        "datasets": datasets
    }
    self.doc(t.render(context))
    return

  def calculate_uplift_smooth(self, quantiles, branch, segment, metric_type, metric):
    control = self.data["branches"][0]

    quantiles_control = self.data[control][segment][metric_type][metric]["quantiles"]
    values_control = self.data[control][segment][metric_type][metric]["quantile_vals"]
    [quantiles_control_n, values_control_n] = cubic_spline_prep(quantiles_control, values_control)
    tck = interpolate.splrep(quantiles_control_n, values_control_n, k=3)
    values_control_n = interpolate.splev(quantiles, tck, der=0)

    quantiles_branch = self.data[branch][segment][metric_type][metric]["quantiles"]
    values_branch = self.data[branch][segment][metric_type][metric]["quantile_vals"]
    [quantiles_branch_n, values_branch_n] = cubic_spline_prep(quantiles_branch, values_branch)
    tck = interpolate.splrep(quantiles_branch_n, values_branch_n, k=3)
    values_branch_n = interpolate.splev(quantiles, tck, der=0)

    uplifts = []
    diffs = []
    for i in range(len(quantiles)):
      diff = values_branch_n[i] - values_control_n[i]
      uplift = diff/values_control_n[i]*100
      diffs.append(diff)
      uplifts.append(uplift)

    return [diffs, uplifts]

  def calculate_uplift_spline(self, quantiles, branch, segment, metric_type, metric):
    control = self.data["branches"][0]

    quantiles_control = self.data[control][segment][metric_type][metric]["quantiles"]
    values_control = self.data[control][segment][metric_type][metric]["quantile_vals"]
    [quantiles_control_n, values_control_n] = cubic_spline_prep(quantiles_control, values_control)
    cs_control = interpolate.CubicSpline(quantiles_control_n, values_control_n)

    quantiles_branch = self.data[branch][segment][metric_type][metric]["quantiles"]
    values_branch = self.data[branch][segment][metric_type][metric]["quantile_vals"]
    [quantiles_branch_n, values_branch_n] = cubic_spline_prep(quantiles_branch, values_branch)
    cs_branch = interpolate.CubicSpline(quantiles_branch_n, values_branch_n)

    uplifts = []
    diffs = []
    for q in quantiles:
      diff = cs_branch(q) - cs_control(q)
      uplift = diff/cs_control(q)*100
      diffs.append(diff)
      uplifts.append(uplift)

    return [diffs, uplifts]


  def calculate_cdf_uplift_spline(self, quantiles, branch, segment, metric_type, metric):
    control = self.data["branches"][0]

    cdf_control = self.data[control][segment][metric_type][metric]["pdf"]["cdf"]
    values_control = self.data[control][segment][metric_type][metric]["pdf"]["values"]
    [cdf_control_n, values_control_n] = cubic_spline_prep(cdf_control, values_control)
    cs_control = CubicSpline(cdf_control_n, values_control_n)

    cdf_branch = self.data[branch][segment][metric_type][metric]["pdf"]["cdf"]
    values_branch = self.data[branch][segment][metric_type][metric]["pdf"]["values"]
    [cdf_branch_n, values_branch_n] = cubic_spline_prep(cdf_branch, values_branch)
    cs_branch = CubicSpline(cdf_branch_n, values_branch_n)

    cdf_uplift = []
    for q in quantiles:
      uplift = (cs_branch(q) - cs_control(q))/cs_control(q)*100
      cdf_uplift.append(uplift)

    return cdf_uplift

  def createUpliftComparison(self, segment, metric, metric_type):
    t = get_template("uplift.html")

    control = self.data["branches"][0]
    quantiles = list(np.around(np.linspace(0.1, 0.99, 90), 2))

    datasets = []
    for branch in self.data["branches"]:
      if branch == control:
        continue

      [diff, uplift] = self.calculate_uplift_smooth(quantiles, branch, segment, metric_type, metric)
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

      if "t-test" in self.data[branch][segment][metric_type][metric]:
        tval = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["t-test"]["score"])
        pval = "{0:.1g}".format(self.data[branch][segment][metric_type][metric]["t-test"]["p-value"])
      else:
        tval = ""
        pval = ""

      dataset = {
          "branch": branch,
          "mean": mean,
          "uplift": uplift,
          "se": se,
          "std": std,
          "tval": tval,
          "pval": pval,
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
    
    # Dump the config used for the experiment
    self.createConfig()

    # Generate charts and tables for each segment and metric
    for segment in self.data['segments']:
      self.createHistogramMetrics(segment)
      self.createPageloadEventMetrics(segment)

    self.endDocument()
    return str(self.doc)
