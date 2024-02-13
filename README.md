# Telemetry Perf Reports

## Overview

Telemetry Perf Reports is a Python project designed for analyzing and generating performance reports based on telemetry data. 

## Dependencies

Ensure you have the following Python libraries installed:

- [NumPy](https://numpy.org/): `pip install numpy`
- [Django](https://www.djangoproject.com/): `pip install django`
- [google-cloud-query]: `pip install google-cloud-bigquery`
- [livestats]: `pip install livestats`
- [airium]: `pip install airium`

Ensure that the Google Cloud, `gcloud` cli is installed and that you are authenticated with a project defined.

## Usage

1. Install the required dependencies.
2. Create and define the experiment configuration file in /configs
3. Run ```python3 generate-perf-report --config {experiment config}```
