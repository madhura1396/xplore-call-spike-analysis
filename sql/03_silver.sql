-- SILVER (= dbt staging): one view per bronze table, NO joins.
-- Renames, trims, type-safe booleans, simple row-level derived flags.
-- Source: workspace.xplore (bronze)  →  Target: workspace.xplore_silver

CREATE SCHEMA IF NOT EXISTS workspace.xplore_silver COMMENT 'Staging layer: cleaned 1:1 views over bronze';

CREATE OR REPLACE VIEW workspace.xplore_silver.stg_technical_calls COMMENT 'Sampled call records (May–Jun 2026)' AS
SELECT
  trim(call_id)                    AS call_id,
  trim(customer_id)                AS customer_id,
  call_date,
  call_month                       AS call_month_start,
  trim(region)                     AS region,
  trim(platform)                   AS platform,
  trim(product)                    AS product,
  trim(customer_segment)           AS customer_segment,
  trim(channel)                    AS channel,
  trim(issue_type)                 AS issue_type,
  repeat_contact_flag = 1          AS is_repeat_contact,
  call_duration_minutes,
  trim(resolution_status)          AS resolution_status,
  trim(customer_sentiment)         AS customer_sentiment,
  trim(customer_sentiment) = 'Negative' AS is_negative_sentiment,
  trim(agent_id)                   AS agent_id   -- kept for lineage only; excluded from gold (no agent evaluation)
FROM workspace.xplore.technical_calls;

CREATE OR REPLACE VIEW workspace.xplore_silver.stg_transcripts COMMENT 'Transcripts + keyword flags (replace missing AI flags, A9)' AS
SELECT
  trim(call_id)                    AS call_id,
  trim(transcript_id)              AS transcript_id,
  transcript_text,
  trim(detected_theme)             AS detected_theme,   -- unreliable (A11): not carried to gold
  trim(ai_sentiment)               AS ai_sentiment,     -- copy of customer_sentiment (A10): not carried to gold
  ai_summary,
  trim(transcript_language)        AS transcript_language,
  transcript_text ILIKE '%regional instability%'                         AS mentions_regional_instability,
  transcript_text ILIKE '%recurring%' OR transcript_text ILIKE '%repeat troubleshooting%' AS mentions_recurring_issue,
  transcript_text ILIKE '%frustration%'                                  AS mentions_frustration,
  transcript_text ILIKE '%outage%'                                       AS mentions_outage,
  transcript_text ILIKE '%wi-fi%'                                        AS mentions_wifi,
  transcript_text ILIKE '%modem%' OR transcript_text ILIKE '%router%' OR transcript_text ILIKE '%extender%' AS mentions_equipment,
  transcript_text RLIKE '(?i)\\bfirmware\\b|\\bupdate\\b' AS mentions_firmware  -- whole words: 'updated appointment' must not match
FROM workspace.xplore.transcripts;

CREATE OR REPLACE VIEW workspace.xplore_silver.stg_voc_feedback COMMENT 'Post-call VOC feedback' AS
SELECT
  trim(feedback_id)                AS feedback_id,
  trim(customer_id)                AS customer_id,
  trim(call_id)                    AS call_id,
  feedback_date,
  csat_score_1_to_5                AS csat_score,
  trim(nps_group)                  AS nps_group,       -- derived from CSAT (A12)
  trim(feedback_topic)             AS feedback_topic,
  verbatim_comment,
  csat_score_1_to_5 >= 4           AS is_satisfied,
  trim(nps_group) = 'Detractor'    AS is_detractor
FROM workspace.xplore.voc_feedback;

CREATE OR REPLACE VIEW workspace.xplore_silver.stg_call_volume_daily COMMENT 'True daily technical call totals (Apr–Jun 2026)' AS
SELECT
  `date`                           AS call_date,
  technical_calls                  AS total_calls
FROM workspace.xplore.call_volume_daily;

CREATE OR REPLACE VIEW workspace.xplore_silver.stg_network_events COMMENT 'Network / firmware events' AS
SELECT
  trim(network_event_id)           AS network_event_id,
  event_date,
  trim(region)                     AS region,
  trim(event_type)                 AS event_type,
  trim(severity)                   AS severity
FROM workspace.xplore.network_events;

CREATE OR REPLACE VIEW workspace.xplore_silver.stg_device_health COMMENT 'Device telemetry snapshot (no join to callers, A4)' AS
SELECT
  trim(customer_id)                AS customer_id,
  trim(firmware_version)           AS firmware_version,
  reboot_count                     AS reboot_count_7d,      -- renamed to dictionary name (A5)
  trim(signal_quality)             AS signal_quality_band   -- renamed to dictionary name (A5)
FROM workspace.xplore.device_health;
