-- Phase 2 — Data profiling: data dictionary vs actual tables
-- Creates 3 snapshot tables in workspace.xplore:
--   dq_data_dictionary     : every column documented in 02_Data_Dictionary.docx
--   dq_schema_comparison   : dictionary columns vs actual table columns (status + type check)
--   dq_table_summary       : one row per table: file present?, column counts, row count

-- 1. Data dictionary as a table (source: 02_Data_Dictionary.docx, 8 tables / 80 columns)
CREATE OR REPLACE TABLE workspace.xplore.dq_data_dictionary (
  table_name STRING, column_position INT, column_name STRING,
  data_type STRING, description STRING, candidate_use STRING
) COMMENT 'Columns documented in 02_Data_Dictionary.docx';

INSERT INTO workspace.xplore.dq_data_dictionary VALUES
  ('technical_calls', 1, 'call_id', 'string', 'Unique synthetic call identifier', 'Join key to transcripts and VOC'),
  ('technical_calls', 2, 'customer_id', 'string', 'Synthetic customer identifier', 'Join key to device health and VOC'),
  ('technical_calls', 3, 'call_date', 'date', 'Date of technical support call', 'Trend and post-event analysis'),
  ('technical_calls', 4, 'call_month', 'string', 'Derived month from call_date', 'Monthly aggregation'),
  ('technical_calls', 5, 'region', 'string', 'Customer/service region', 'Regional impact analysis'),
  ('technical_calls', 6, 'platform', 'string', 'Technology/platform', 'Platform impact analysis'),
  ('technical_calls', 7, 'product', 'string', 'Synthetic internet product/package', 'Product impact analysis'),
  ('technical_calls', 8, 'customer_segment', 'string', 'Synthetic customer segment', 'Customer segment analysis'),
  ('technical_calls', 9, 'channel', 'string', 'Interaction channel', 'Contact channel analysis'),
  ('technical_calls', 10, 'issue_type', 'string', 'Primary reason for contact', 'Main call-driver analysis'),
  ('technical_calls', 11, 'repeat_contact_flag', 'integer', '1 if repeat contact indicator, otherwise 0', 'Repeat-contact KPI'),
  ('technical_calls', 12, 'previous_contact_count', 'integer', 'Number of prior related contacts in recent period', 'Depth of repeat-contact behavior'),
  ('technical_calls', 13, 'call_duration_minutes', 'integer', 'Call duration in minutes', 'Operational effort and complexity'),
  ('technical_calls', 14, 'resolution_status', 'string', 'Outcome/resolution status', 'Resolution mix and action analysis'),
  ('technical_calls', 15, 'customer_sentiment', 'string', 'High-level sentiment label', 'Customer experience signal'),
  ('technical_calls', 16, 'agent_id', 'string', 'Synthetic agent identifier', 'Optional segmentation; do not evaluate individual agents'),
  ('technical_calls', 17, 'firmware_version', 'string', 'Firmware version associated with customer equipment', 'Root-cause segmentation'),
  ('technical_calls', 18, 'modem_model', 'string', 'Synthetic equipment model', 'Device/equipment segmentation'),
  ('technical_calls', 19, 'signal_quality_band', 'string', 'High/Medium/Low signal-quality band', 'Service health indicator'),
  ('technical_calls', 20, 'network_event_id', 'string', 'Synthetic network or firmware event identifier', 'Join to network_events.csv'),
  ('technical_calls', 21, 'previous_tech_visit_flag', 'integer', '1 if prior technician visit occurred', 'Repeat repair / operational impact signal'),
  ('transcripts', 1, 'call_id', 'string', 'Unique synthetic call identifier', 'Join to technical calls'),
  ('transcripts', 2, 'transcript_id', 'string', 'Synthetic transcript identifier', 'Transcript record key'),
  ('transcripts', 3, 'transcript_text', 'string', 'Synthetic transcript-like call note', 'Qualitative evidence'),
  ('transcripts', 4, 'detected_theme', 'string', 'Synthetic detected theme', 'Theme analysis'),
  ('transcripts', 5, 'ai_sentiment', 'string', 'Synthetic AI sentiment label', 'Customer sentiment support'),
  ('transcripts', 6, 'ai_summary', 'string', 'Synthetic AI-generated summary', 'Summary review'),
  ('transcripts', 7, 'transcript_language', 'string', 'Synthetic language indicator', 'Language distribution'),
  ('transcripts', 8, 'root_cause_prediction', 'string', 'Synthetic AI-predicted root cause', 'Supporting evidence, not absolute truth'),
  ('transcripts', 9, 'firmware_issue_flag', 'integer', '1 if transcript suggests firmware-related issue', 'Root-cause support'),
  ('transcripts', 10, 'outage_mentioned_flag', 'integer', '1 if outage is mentioned', 'Outage hypothesis support'),
  ('transcripts', 11, 'wifi_issue_flag', 'integer', '1 if Wi-Fi issue is mentioned', 'Issue classification support'),
  ('transcripts', 12, 'escalation_reason', 'string', 'Reason for escalation, if any', 'Process-driver analysis'),
  ('transcripts', 13, 'customer_effort_score', 'integer', 'Synthetic effort score; higher means more effort', 'Customer effort analysis'),
  ('transcripts', 14, 'churn_risk', 'string', 'Synthetic churn-risk label', 'Customer risk support'),
  ('voc_feedback', 1, 'feedback_id', 'string', 'Synthetic feedback identifier', 'VOC record key'),
  ('voc_feedback', 2, 'customer_id', 'string', 'Synthetic customer identifier', 'Join to technical calls/device health'),
  ('voc_feedback', 3, 'call_id', 'string', 'Unique synthetic call identifier', 'Join to technical calls'),
  ('voc_feedback', 4, 'feedback_date', 'date', 'Date of feedback', 'Post-call experience trend'),
  ('voc_feedback', 5, 'csat_score_1_to_5', 'integer', 'Synthetic CSAT score from 1 to 5', 'Customer satisfaction KPI'),
  ('voc_feedback', 6, 'nps_group', 'string', 'Synthetic NPS grouping', 'Customer advocacy signal'),
  ('voc_feedback', 7, 'feedback_topic', 'string', 'Feedback topic', 'VOC issue analysis'),
  ('voc_feedback', 8, 'verbatim_comment', 'string', 'Synthetic customer comment', 'Qualitative support'),
  ('voc_feedback', 9, 'resolution_rating', 'integer', 'Synthetic rating of resolution experience', 'Resolution quality'),
  ('voc_feedback', 10, 'customer_effort_score', 'integer', 'Synthetic effort score', 'Effort and friction indicator'),
  ('voc_feedback', 11, 'likelihood_to_call_again', 'string', 'Synthetic likelihood to call again', 'Repeat-demand signal'),
  ('voc_feedback', 12, 'issue_resolved_flag', 'integer', '1 if customer indicates issue resolved', 'Resolution effectiveness'),
  ('call_volume_daily', 1, 'date', 'date', 'Calendar date', 'Time-series x-axis'),
  ('call_volume_daily', 2, 'technical_calls', 'integer', 'Daily number of technical calls', 'Spike detection'),
  ('call_volume_daily', 3, 'baseline_expected_calls', 'integer', 'Synthetic expected baseline calls', 'Compare actual vs expected'),
  ('call_volume_daily', 4, 'call_rate_per_1000_customers', 'float', 'Daily call rate normalized to active base', 'Normalized trend analysis'),
  ('network_events', 1, 'network_event_id', 'string', 'Synthetic network event identifier', 'Join key'),
  ('network_events', 2, 'event_date', 'date', 'Date event started', 'Event timing'),
  ('network_events', 3, 'region', 'string', 'Region impacted by event', 'Regional correlation'),
  ('network_events', 4, 'platform', 'string', 'Technology/platform impacted', 'Platform correlation'),
  ('network_events', 5, 'event_type', 'string', 'Event category such as Firmware Update or Rollback', 'Root-cause hypothesis'),
  ('network_events', 6, 'firmware_version', 'string', 'Firmware involved in event', 'Firmware linkage'),
  ('network_events', 7, 'severity', 'string', 'Synthetic severity label', 'Prioritization'),
  ('network_events', 8, 'affected_customers', 'integer', 'Synthetic count of impacted customers', 'Scale of impact'),
  ('network_events', 9, 'event_status', 'string', 'Open, monitoring, resolved, rollback, etc.', 'Event lifecycle'),
  ('device_health', 1, 'customer_id', 'string', 'Synthetic customer identifier', 'Join to technical calls'),
  ('device_health', 2, 'firmware_version', 'string', 'Firmware version on customer equipment', 'Root-cause segmentation'),
  ('device_health', 3, 'modem_model', 'string', 'Synthetic modem/device model', 'Device segmentation'),
  ('device_health', 4, 'reboot_count_7d', 'integer', 'Number of device reboots in prior 7 days', 'Instability indicator'),
  ('device_health', 5, 'signal_quality_score', 'float', 'Synthetic signal quality score', 'Service health indicator'),
  ('device_health', 6, 'signal_quality_band', 'string', 'High/Medium/Low signal band', 'Simplified service health filter'),
  ('device_health', 7, 'last_firmware_update_date', 'date', 'Date firmware was last updated', 'Timing validation'),
  ('device_health', 8, 'days_since_install', 'integer', 'Synthetic days since install', 'Installation-age analysis'),
  ('customer_base_daily', 1, 'date', 'date', 'Calendar date', 'Join to volume by date'),
  ('customer_base_daily', 2, 'active_customers', 'integer', 'Synthetic active customer base', 'Normalize call volume'),
  ('customer_base_daily', 3, 'active_customers_fixed_wireless', 'integer', 'Synthetic active Fixed Wireless base', 'Platform-specific call rate'),
  ('customer_base_daily', 4, 'active_customers_fibre', 'integer', 'Synthetic active Fibre base', 'Platform-specific call rate'),
  ('truck_rolls', 1, 'truck_roll_id', 'string', 'Synthetic technician dispatch identifier', 'Truck roll key'),
  ('truck_rolls', 2, 'call_id', 'string', 'Related synthetic call identifier', 'Join to call'),
  ('truck_rolls', 3, 'customer_id', 'string', 'Synthetic customer identifier', 'Customer impact'),
  ('truck_rolls', 4, 'dispatch_date', 'date', 'Date technician dispatch was scheduled', 'Operational impact timing'),
  ('truck_rolls', 5, 'region', 'string', 'Region of dispatch', 'Regional operational impact'),
  ('truck_rolls', 6, 'dispatch_reason', 'string', 'Reason for dispatch', 'Operational driver'),
  ('truck_rolls', 7, 'completed_flag', 'integer', '1 if completed', 'Completion status'),
  ('truck_rolls', 8, 'repeat_dispatch_flag', 'integer', '1 if repeat dispatch', 'Repeat repair signal');

-- 2. Column-level comparison
CREATE OR REPLACE TABLE workspace.xplore.dq_schema_comparison
COMMENT 'Dictionary columns vs actual loaded columns' AS
WITH actual AS (
  SELECT table_name, column_name, ordinal_position + 1 AS actual_position, data_type AS actual_type
  FROM workspace.information_schema.columns
  WHERE table_schema = 'xplore' AND table_name IN ('technical_calls','transcripts','voc_feedback','call_volume_daily','network_events','device_health')
),
loaded AS (SELECT DISTINCT table_name FROM actual)
SELECT
  coalesce(d.table_name, a.table_name)   AS table_name,
  coalesce(d.column_name, a.column_name) AS column_name,
  d.column_position                      AS dictionary_position,
  a.actual_position,
  d.data_type                            AS dictionary_type,
  a.actual_type,
  CASE
    WHEN d.column_name IS NOT NULL AND a.column_name IS NOT NULL THEN 'present'
    WHEN a.column_name IS NULL AND l.table_name IS NULL          THEN 'missing_table'
    WHEN a.column_name IS NULL                                   THEN 'missing_column'
    ELSE 'not_in_dictionary'
  END AS status,
  CASE
    WHEN d.column_name IS NULL OR a.column_name IS NULL THEN NULL
    WHEN lower(d.data_type) = 'string'  AND a.actual_type = 'STRING' THEN true
    WHEN lower(d.data_type) = 'date'    AND a.actual_type = 'DATE' THEN true
    WHEN lower(d.data_type) = 'integer' AND a.actual_type IN ('INT','BIGINT','SMALLINT','TINYINT') THEN true
    WHEN lower(d.data_type) = 'float'   AND a.actual_type IN ('DOUBLE','FLOAT','DECIMAL') THEN true
    ELSE false
  END AS type_matches,
  d.description,
  d.candidate_use,
  current_timestamp() AS snapshot_at
FROM workspace.xplore.dq_data_dictionary d
FULL OUTER JOIN actual a
  ON d.table_name = a.table_name AND d.column_name = a.column_name
LEFT JOIN loaded l ON l.table_name = coalesce(d.table_name, a.table_name);

-- 3. Table-level summary
CREATE OR REPLACE TABLE workspace.xplore.dq_table_summary
COMMENT 'Per-table snapshot: dictionary vs loaded data' AS
WITH counts AS (
  SELECT 'technical_calls' AS table_name, count(*) AS row_count FROM workspace.xplore.technical_calls
  UNION ALL SELECT 'transcripts',       count(*) FROM workspace.xplore.transcripts
  UNION ALL SELECT 'voc_feedback',      count(*) FROM workspace.xplore.voc_feedback
  UNION ALL SELECT 'call_volume_daily', count(*) FROM workspace.xplore.call_volume_daily
  UNION ALL SELECT 'network_events',    count(*) FROM workspace.xplore.network_events
  UNION ALL SELECT 'device_health',     count(*) FROM workspace.xplore.device_health
)
SELECT
  c.table_name,
  max(c.status <> 'missing_table')                         AS file_provided,
  count_if(c.dictionary_position IS NOT NULL)              AS dictionary_columns,
  count_if(c.status = 'present')                           AS present_columns,
  count_if(c.status IN ('missing_column','missing_table')) AS missing_columns,
  count_if(c.status = 'not_in_dictionary')                 AS extra_columns,
  count_if(c.type_matches = false)                         AS type_mismatches,
  round(100 * count_if(c.status = 'present') / nullif(count_if(c.dictionary_position IS NOT NULL), 0), 1) AS pct_columns_present,
  concat_ws(', ', array_sort(collect_list(CASE WHEN c.status IN ('missing_column','missing_table') THEN c.column_name END))) AS missing_column_list,
  concat_ws(', ', array_sort(collect_list(CASE WHEN c.status = 'not_in_dictionary' THEN c.column_name END)))               AS extra_column_list,
  max(n.row_count)                                         AS row_count,
  current_timestamp()                                      AS snapshot_at
FROM workspace.xplore.dq_schema_comparison c
LEFT JOIN counts n ON n.table_name = c.table_name
GROUP BY c.table_name;

-- 4. View results
SELECT * FROM workspace.xplore.dq_table_summary ORDER BY file_provided DESC, table_name;
SELECT * FROM workspace.xplore.dq_schema_comparison WHERE status <> 'present' OR type_matches = false ORDER BY table_name, dictionary_position;
