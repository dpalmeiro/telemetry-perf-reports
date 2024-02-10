{% autoescape off %}
with eventdata as (
SELECT
  normalized_os as segment,
  mozfun.map.get_key(ping_info.experiments, "{{slug}}").branch as branch,
  SAFE_CAST((SELECT value FROM UNNEST(event.extra) WHERE key = '{{metric}}') AS int) AS {{metric}},
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
  {{metric}} as bucket,
  COUNT(*) as counts
FROM
  eventdata
WHERE
  {{metric}} >= {{minVal}} AND {{metric}} <= {{maxVal}}
GROUP BY
  segment, branch, bucket
ORDER BY
  segment, branch, bucket
{% endautoescape %}
