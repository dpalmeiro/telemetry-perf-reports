{% autoescape off %}
with 
desktop_data as (
    SELECT 
        normalized_os as segment,
        mozfun.map.get_key(ping_info.experiments, "{{slug}}").branch as branch,
        CAST(key as INT64)/1000000 AS bucket,
        value as count
    FROM `mozdata.firefox_desktop.metrics` as d
      CROSS JOIN UNNEST({{histogram}}.values)
    WHERE
      DATE(submission_timestamp) >= DATE('{{startDate}}')
      AND DATE(submission_timestamp) <= DATE('{{endDate}}')
      AND normalized_channel = "{{channel}}"
      AND normalized_app_name = "Firefox"
      AND {{histogram}} is not null
      AND ARRAY_LENGTH(ping_info.experiments) > 0
      AND mozfun.map.get_key(ping_info.experiments, "{{slug}}").branch is not null
      {% for isp in blacklist %}
      AND metadata.isp.name != "{{isp}}"
      {% endfor %}
),
android_data as (
    SELECT 
        normalized_os as segment,
        mozfun.map.get_key(ping_info.experiments, "{{slug}}").branch as branch,
        CAST(key as INT64)/1000000 AS bucket,
        value as count
    FROM `mozdata.fenix.metrics` as f
      CROSS JOIN UNNEST({{histogram}}.values)
    WHERE
      DATE(submission_timestamp) >= DATE('{{startDate}}')
      AND DATE(submission_timestamp) <= DATE('{{endDate}}')
      AND normalized_channel = "{{channel}}"
      AND {{histogram}} is not null
      AND ARRAY_LENGTH(ping_info.experiments) > 0
      AND mozfun.map.get_key(ping_info.experiments, "{{slug}}").branch is not null
      {% for isp in blacklist %}
      AND metadata.isp.name != "{{isp}}"
      {% endfor %}
)
{% if include_null_branch == True %}
,desktop_data_null as (
    SELECT 
        normalized_os as segment,
        "null" as branch,
        CAST(key as INT64)/1000000 AS bucket,
        value as count
    FROM `mozdata.firefox_desktop.metrics` as d
      CROSS JOIN UNNEST({{histogram}}.values)
    WHERE
      DATE(submission_timestamp) >= DATE('{{startDate}}')
      AND DATE(submission_timestamp) <= DATE('{{endDate}}')
      AND normalized_channel = "{{channel}}"
      AND normalized_app_name = "Firefox"
      AND {{histogram}} is not null
      AND ARRAY_LENGTH(ping_info.experiments) = 0
),
android_data_null as (
    SELECT 
        normalized_os as segment,
        "null" as branch,
        CAST(key as INT64)/1000000 AS bucket,
        value as count
    FROM `mozdata.fenix.metrics` as f
      CROSS JOIN UNNEST({{histogram}}.values)
    WHERE
      DATE(submission_timestamp) >= DATE('{{startDate}}')
      AND DATE(submission_timestamp) <= DATE('{{endDate}}')
      AND normalized_channel = "{{channel}}"
      AND {{histogram}} is not null
      AND ARRAY_LENGTH(ping_info.experiments) = 0
)
{% endif %}

SELECT
    segment,
    branch,
    bucket,
    SUM(count) as counts
FROM
    (
        SELECT * FROM desktop_data
        UNION ALL
        SELECT * FROM android_data
{% if include_null_branch == True %}
        UNION ALL
        SELECT * FROM desktop_data_null
        UNION ALL
        SELECT * FROM android_data_null
{% endif %}
    ) s
GROUP BY
  segment, branch, bucket
ORDER BY
  segment, branch, bucket
{% endautoescape %}
