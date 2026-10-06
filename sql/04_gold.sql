-- GOLD (= dbt marts): joins + business logic. What the dashboard/app read.
-- Source: workspace.xplore_silver  →  Target: workspace.xplore_gold
-- Two facts at different grains — never join them to each other:
--   fct_daily_volume : true totals, 1 row/day  → HOW MUCH / WHEN
--   fct_calls        : sampled calls, 1 row/call → WHO / WHAT (mix)
-- Periods and sample weights are added in Python (app/data.py, analysis scripts), not here.
-- Planned improvement (from the reviews): add `period` and `sample_weight` columns to gold so every consumer
-- shares one definition.

CREATE SCHEMA IF NOT EXISTS workspace.xplore_gold COMMENT 'Analytics layer: facts and dimensions';

-- dim_date: one row per day across the full daily-volume range
CREATE OR REPLACE VIEW workspace.xplore_gold.dim_date COMMENT 'Calendar dimension' AS
WITH bounds AS (SELECT min(call_date) AS d0, max(call_date) AS d1 FROM workspace.xplore_silver.stg_call_volume_daily)
SELECT
  d                                   AS date_key,
  date_format(d, 'EEEE')              AS day_name,
  dayofweek(d)                        AS day_of_week_num,     -- 1 = Sunday
  dayofweek(d) IN (1, 7)              AS is_weekend,
  date_trunc('WEEK', d)::DATE         AS week_start,          -- Monday
  trunc(d, 'MM')                      AS month_start,
  date_format(d, 'yyyy-MM')           AS month_label
FROM bounds LATERAL VIEW explode(sequence(d0, d1, INTERVAL 1 DAY)) AS d;

-- dim_region: every region, with its firmware event if any (regions without one = control group)
CREATE OR REPLACE VIEW workspace.xplore_gold.dim_region COMMENT 'Region dimension with network/firmware event' AS
WITH regions AS (
  SELECT region FROM workspace.xplore_silver.stg_technical_calls
  UNION SELECT region FROM workspace.xplore_silver.stg_network_events
)
SELECT
  r.region,
  e.network_event_id,
  e.event_date                        AS region_event_date,
  e.event_type                        AS region_event_type,
  e.severity                          AS region_event_severity,
  e.network_event_id IS NOT NULL      AS region_has_event
FROM regions r
LEFT JOIN workspace.xplore_silver.stg_network_events e ON e.region = r.region;

-- fct_calls: one row per sampled call, enriched with transcript, VOC and region event context
CREATE OR REPLACE VIEW workspace.xplore_gold.fct_calls COMMENT 'Call-level fact (sample). Excludes agent_id, ai_sentiment, detected_theme' AS
SELECT
  c.call_id, c.customer_id, c.call_date, c.call_month_start,
  d.week_start, d.day_name, d.is_weekend,
  c.region, c.platform, c.product, c.customer_segment, c.channel, c.issue_type,
  c.is_repeat_contact, c.call_duration_minutes, c.resolution_status,
  c.customer_sentiment, c.is_negative_sentiment,
  -- region event context (link by region + date, A3)
  r.region_has_event, r.network_event_id, r.region_event_date, r.region_event_severity,
  datediff(c.call_date, r.region_event_date)                  AS days_since_region_event,
  coalesce(c.call_date >= r.region_event_date, false)         AS is_after_region_event,
  -- transcript
  t.transcript_id, t.transcript_language, t.ai_summary,
  t.mentions_regional_instability, t.mentions_recurring_issue, t.mentions_frustration,
  t.mentions_outage, t.mentions_wifi, t.mentions_equipment, t.mentions_firmware,
  -- VOC (56% coverage)
  v.feedback_id IS NOT NULL                                   AS has_feedback,
  v.feedback_id, v.csat_score, v.nps_group, v.is_satisfied, v.is_detractor, v.verbatim_comment
FROM workspace.xplore_silver.stg_technical_calls c
LEFT JOIN workspace.xplore_silver.stg_transcripts  t ON t.call_id = c.call_id
LEFT JOIN workspace.xplore_silver.stg_voc_feedback v ON v.call_id = c.call_id
LEFT JOIN workspace.xplore_gold.dim_region         r ON r.region  = c.region
LEFT JOIN workspace.xplore_gold.dim_date           d ON d.date_key = c.call_date;

-- fct_daily_volume: one row per day — true totals + sample coverage + event markers
CREATE OR REPLACE VIEW workspace.xplore_gold.fct_daily_volume COMMENT 'Daily fact: true totals, 7-day avg, sampled calls, events' AS
WITH sampled AS (
  SELECT call_date, count(*) AS sampled_calls FROM workspace.xplore_gold.fct_calls GROUP BY call_date
),
events AS (
  SELECT event_date, concat_ws(', ', collect_list(concat(region, ' (', severity, ')'))) AS events_on_day
  FROM workspace.xplore_silver.stg_network_events GROUP BY event_date
)
SELECT
  d.date_key                                      AS call_date,
  d.day_name, d.is_weekend, d.week_start, d.month_start,
  v.total_calls,
  round(avg(v.total_calls) OVER (ORDER BY d.date_key ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS total_calls_7d_avg,
  coalesce(s.sampled_calls, 0)                    AS sampled_calls,
  round(coalesce(s.sampled_calls, 0) / v.total_calls, 3) AS sample_ratio,
  e.events_on_day,
  e.event_date IS NOT NULL                        AS is_event_day
FROM workspace.xplore_gold.dim_date d
LEFT JOIN workspace.xplore_silver.stg_call_volume_daily v ON v.call_date = d.date_key
LEFT JOIN sampled s ON s.call_date = d.date_key
LEFT JOIN events  e ON e.event_date = d.date_key;

-- fct_device_health: standalone telemetry snapshot (cannot join to callers, A4)
CREATE OR REPLACE VIEW workspace.xplore_gold.fct_device_health COMMENT 'Device telemetry snapshot — standalone, no caller link' AS
SELECT customer_id, firmware_version, reboot_count_7d, signal_quality_band
FROM workspace.xplore_silver.stg_device_health;
