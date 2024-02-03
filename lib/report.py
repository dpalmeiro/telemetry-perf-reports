import json
import os
import numpy as np
from django.template import Template, Context
from django.template.loader import get_template
from airium import Airium

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

  def createQuantileComparison(self, segment, metric, metric_type):
    t = get_template("quantile.html")

    control = self.data["branches"][0]
    quantiles = list(self.data[control][segment][metric_type][metric]["quantile"].keys())
    values_control = list(self.data[control][segment][metric_type][metric]["quantile"].values())

    datasets = []
    for branch in self.data["branches"]:
      if branch == control:
        continue
      values = list(self.data[branch][segment][metric_type][metric]["quantile"].values())

      uplift = []
      diff = []
      for i in range(len(values)):
        x1 = values[i]
        x2 = values_control[i]
        if x2 == 0:
          up = 0
        else :
          up = (x1-x2)/x2*100
        uplift.append(up)
        diff.append(x1-x2)

      #uplift = [((x1-x2)/x2*100) for (x1, x2) in zip(values, values_control)]
      dataset = {
          "branch": branch,
          "diff": diff,
          "uplift": uplift
      }
      datasets.append(dataset)

    context = {
        "segment": segment,
        "metric": metric,
        "quantiles": quantiles,
        "datasets": datasets
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
      yMin = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["confidence"]["min"])
      yMax = "{0:.1f}".format(self.data[branch][segment][metric_type][metric]["confidence"]["max"])

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
          "yMin": yMin,
          "yMax": yMax
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
    # Add PDF and CDF comparison
    self.createCDFComparison(segment, metric, metric_type)
    # Add quantile comparison
    self.createQuantileComparison(segment, metric, metric_type)
    # Add mean comparison
    self.createMeanComparison(segment, metric, metric_type)

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
