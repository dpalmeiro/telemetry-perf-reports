{% autoescape off %}
with 
{% for branch in branches %}
eventdata_{{branch.name}} as (
    SELECT
        normalized_os as segment,
        SAFE_CAST((SELECT value FROM UNNEST(event.extra) WHERE key = '{{metric}}') AS int) AS {{metric}},
    FROM
        `moz-fx-data-shared-prod.firefox_desktop.pageload`
    CROSS JOIN
      UNNEST(events) AS event
    WHERE
        DATE(submission_timestamp) >= DATE('{{branch.startDate}}')
        AND DATE(submission_timestamp) <= DATE('{{branch.endDate}}')
        AND normalized_channel = "{{branch.channel}}"
        AND normalized_app_name = "Firefox"
{% for condition in branch.conditions %}
        {{condition}}
{% endfor %}
),
aggregate_{{branch.name}} as (
SELECT
    segment,
    "{{branch.name}}" as branch,
    {{metric}} as bucket,
    COUNT(*) as counts
FROM
    eventdata_{{branch.name}}
WHERE
    {{metric}} > {{minVal}} AND {{metric}} < {{maxVal}}
GROUP BY
    segment, branch, bucket
ORDER BY
    segment, branch, bucket
)
{% if branch.last == False %}
,
{% endif %}
{% endfor %}

SELECT
    segment,
    branch,
    bucket,
    counts
FROM
    (
{% for branch in branches %}
        SELECT * FROM aggregate_{{branch.name}}
{% if branch.last == False %}
        UNION ALL
{% endif %}
{% endfor %}
    )
ORDER BY
    segment, branch, bucket
{% endautoescape %}
