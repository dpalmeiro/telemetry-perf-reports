{% autoescape off %}
WITH buckets as (
SELECT
    i as bucket
FROM
    UNNEST(generate_array({{minBucket}}, {{maxBucket}})) i
),
eventdata as (
SELECT
  normalized_os as segment,
  mozfun.map.get_key(ping_info.experiments, "{{slug}}").branch as branch,
{% for metric in metrics %}
  SAFE_CAST((SELECT value FROM UNNEST(event.extra) WHERE key = '{{metric}}') AS int) AS {{metric}},
{% endfor %}
FROM
  `moz-fx-data-shared-prod.firefox_desktop.pageload`
CROSS JOIN
  UNNEST(events) AS event
WHERE
  normalized_channel = "{{channel}}"
  AND DATE(submission_timestamp) >= DATE('{{startDate}}')
  AND DATE(submission_timestamp) <= DATE('{{endDate}}')  
  AND mozfun.map.get_key(ping_info.experiments, "{{slug}}").branch is not null
)
SELECT
  segment,
  branch,
  bucket,
{% for metric in metrics %}
    COUNTIF({{metric}} = bucket) as {{metric}}_counts,
{% endfor %}
FROM
  eventdata, buckets
WHERE
  load_time > 0
GROUP BY
  segment, branch, bucket
ORDER BY
  segment, branch, bucket
{% endautoescape %}
