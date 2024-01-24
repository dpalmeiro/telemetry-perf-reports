import django
import json
import os
from django.conf import settings
from django.template import Template, Context
from django.template.loader import get_template
from airium import Airium

def calculateCDF(values, density):
  cdf = []
  prevVal = 0
  for i in range(1, len(values)-1):
    width  = (values[i+1]-values[i-1])/2
    cdf_val = prevVal+density[i]*width
    prevVal = cdf_val
    cdf.append(cdf_val)
  return cdf

class ReportGenerator:
  def setupDjango(self):
    TEMPLATES = [
        {
          "BACKEND": "django.template.backends.django.DjangoTemplates",
          'DIRS': [os.path.join(os.path.dirname(__file__),'templates')]
          }
        ]
    settings.configure(TEMPLATES=TEMPLATES)
    django.setup()

  def __init__(self, data):
    self.setupDjango()
    self.data = data
    self.doc = Airium()
    self.iconMap = {
      "All": "fa-globe",
      "Windows": "fa-windows",
      "Linux": "fa-linux",
      "Macintosh": "fa-apple"
    }

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
                "icon": self.iconMap[segment],
                "pageload_metrics" : []
              }
      for metric in self.data['pageload_event_fields']:
        entry["pageload_metrics"].append(metric)
      segments.append(entry)

    ctx = {
        "segments": segments
    }
    self.doc(t.render(ctx))

  def createConfig(self):
    t = get_template("config.html")
    context = { "config": json.dumps(self.data["input"], indent=4) }
    self.doc(t.render(context))

  def createCDFComparison(self, segment, metric):
    t = get_template("cdf.html")

    datasets = []
    for branch in self.data["branches"]:
      values = self.data[branch][segment][metric]["pdf"]["values"]
      density = self.data[branch][segment][metric]["pdf"]["density"]
      cdf = calculateCDF(values, density)

      dataset = {
          "branch": branch,
          "cdf": cdf,
          "density": density
      }
      datasets.append(dataset)

    context = {
        "segment": segment,
        "metric": metric,
        "values": values,
        "datasets": datasets
    }
    self.doc(t.render(context))
    return

  def createQuantileComparison(self, segment, metric):
    t = get_template("quantile.html")

    control = self.data["branches"][0]
    quantiles = list(self.data[control][segment][metric]["quantile"].keys())
    values_control = list(self.data[control][segment][metric]["quantile"].values())

    datasets = []
    for branch in self.data["branches"]:
      if branch == control:
        continue
      values = list(self.data[branch][segment][metric]["quantile"].values())
      diff = [x1 - x2 for (x1, x2) in zip(values, values_control)]
      uplift = [((x1-x2)/x2*100) for (x1, x2) in zip(values, values_control)]
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

  def createMeanComparison(self, segment, metric):
    t = get_template("mean.html")

    datasets = []
    control=self.data["branches"][0]
    for branch in self.data["branches"]:
      mean = "{0:.1f}".format(self.data[branch][segment][metric]["mean"])

      if branch != control:
        branch_mean = self.data[branch][segment][metric]["mean"]
        control_mean = self.data[control][segment][metric]["mean"]
        uplift = (branch_mean-control_mean)/control_mean*100.0
        uplift = "{0:.1f}".format(uplift)
      else:
        uplift = ""


      se   = "{0:.1f}".format(self.data[branch][segment][metric]["se"])
      std  = "{0:.1f}".format(self.data[branch][segment][metric]["std"])
      yMin = "{0:.1f}".format(self.data[branch][segment][metric]["confidence"]["min"])
      yMax = "{0:.1f}".format(self.data[branch][segment][metric]["confidence"]["max"])

      if "t-test" in self.data[branch][segment][metric]:
        tval = "{0:.1f}".format(self.data[branch][segment][metric]["t-test"]["score"])
        pval = "{0:.1g}".format(self.data[branch][segment][metric]["t-test"]["p-value"])
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

  def createHTMLReport(self):
    self.createHeader()
    self.createSidebar()
    
    # Dump the config used for the experiment
    self.createConfig()

    # Generate charts and tables for each segment and metric
    for segment in self.data['segments']:
      for metric in self.data['pageload_event_fields']:
        with self.doc.div(id=f"{segment}-{metric}", klass="cell"):

          # Add title for metric
          with self.doc.div(klass="title"):
            self.doc(f"({segment}) - {metric}")
  
          # Add PDF and CDF comparison
          self.createCDFComparison(segment, metric)

          # Add quantile comparison
          self.createQuantileComparison(segment, metric)

          # Add mean comparison
          self.createMeanComparison(segment, metric)

    self.endDocument()
    return str(self.doc)
