-- Phase 2.3 — Column health for every column in the 6 source tables
-- Output: workspace.xplore.dq_column_health (one row per column)
-- Checks: nulls, blanks, distinct/duplicate keys, case/whitespace variants, ranges, domain rules, top values
-- health_status: FAIL = duplicate key / domain violation / fully null; WARN = nulls, blanks, variants, constant; OK otherwise
-- Structure: one SELECT block per column (41 blocks joined by UNION ALL), all with the same output columns;
-- each block sets that column's expected uniqueness and domain rule (e.g. 'value >= 0', 'not in the future').

CREATE OR REPLACE TABLE workspace.xplore.dq_column_health
COMMENT 'Per-column data health snapshot for source tables' AS
WITH stats AS (
SELECT 'call_volume_daily' AS table_name, 'date' AS column_name, 'DATE' AS data_type, 1 AS column_position,
  true AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'not in the future' AS domain_rule,
  count_if(c > current_date()) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `date` AS v, count(*) AS n FROM workspace.xplore.call_volume_daily GROUP BY `date`)) AS top_values
FROM (SELECT `date` AS c FROM workspace.xplore.call_volume_daily)
UNION ALL
SELECT 'call_volume_daily' AS table_name, 'technical_calls' AS column_name, 'INT' AS data_type, 2 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  round(avg(c), 2) AS avg_value,
  CAST(percentile_approx(c, 0.5) AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'value >= 0' AS domain_rule,
  count_if(c < 0) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `technical_calls` AS v, count(*) AS n FROM workspace.xplore.call_volume_daily GROUP BY `technical_calls`)) AS top_values
FROM (SELECT `technical_calls` AS c FROM workspace.xplore.call_volume_daily)
UNION ALL
SELECT 'device_health' AS table_name, 'customer_id' AS column_name, 'STRING' AS data_type, 1 AS column_position,
  true AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^CU[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^CU[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `customer_id` AS v, count(*) AS n FROM workspace.xplore.device_health GROUP BY `customer_id`)) AS top_values
FROM (SELECT `customer_id` AS c FROM workspace.xplore.device_health)
UNION ALL
SELECT 'device_health' AS table_name, 'firmware_version' AS column_name, 'STRING' AS data_type, 2 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `firmware_version` AS v, count(*) AS n FROM workspace.xplore.device_health GROUP BY `firmware_version`)) AS top_values
FROM (SELECT `firmware_version` AS c FROM workspace.xplore.device_health)
UNION ALL
SELECT 'device_health' AS table_name, 'reboot_count' AS column_name, 'INT' AS data_type, 3 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  round(avg(c), 2) AS avg_value,
  CAST(percentile_approx(c, 0.5) AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'value >= 0' AS domain_rule,
  count_if(c < 0) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `reboot_count` AS v, count(*) AS n FROM workspace.xplore.device_health GROUP BY `reboot_count`)) AS top_values
FROM (SELECT `reboot_count` AS c FROM workspace.xplore.device_health)
UNION ALL
SELECT 'device_health' AS table_name, 'signal_quality' AS column_name, 'STRING' AS data_type, 4 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `signal_quality` AS v, count(*) AS n FROM workspace.xplore.device_health GROUP BY `signal_quality`)) AS top_values
FROM (SELECT `signal_quality` AS c FROM workspace.xplore.device_health)
UNION ALL
SELECT 'network_events' AS table_name, 'network_event_id' AS column_name, 'STRING' AS data_type, 1 AS column_position,
  true AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^NE[0-9]{3}$' AS domain_rule,
  count_if(NOT c RLIKE '^NE[0-9]{3}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `network_event_id` AS v, count(*) AS n FROM workspace.xplore.network_events GROUP BY `network_event_id`)) AS top_values
FROM (SELECT `network_event_id` AS c FROM workspace.xplore.network_events)
UNION ALL
SELECT 'network_events' AS table_name, 'event_date' AS column_name, 'DATE' AS data_type, 2 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'not in the future' AS domain_rule,
  count_if(c > current_date()) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `event_date` AS v, count(*) AS n FROM workspace.xplore.network_events GROUP BY `event_date`)) AS top_values
FROM (SELECT `event_date` AS c FROM workspace.xplore.network_events)
UNION ALL
SELECT 'network_events' AS table_name, 'region' AS column_name, 'STRING' AS data_type, 3 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `region` AS v, count(*) AS n FROM workspace.xplore.network_events GROUP BY `region`)) AS top_values
FROM (SELECT `region` AS c FROM workspace.xplore.network_events)
UNION ALL
SELECT 'network_events' AS table_name, 'event_type' AS column_name, 'STRING' AS data_type, 4 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `event_type` AS v, count(*) AS n FROM workspace.xplore.network_events GROUP BY `event_type`)) AS top_values
FROM (SELECT `event_type` AS c FROM workspace.xplore.network_events)
UNION ALL
SELECT 'network_events' AS table_name, 'severity' AS column_name, 'STRING' AS data_type, 5 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `severity` AS v, count(*) AS n FROM workspace.xplore.network_events GROUP BY `severity`)) AS top_values
FROM (SELECT `severity` AS c FROM workspace.xplore.network_events)
UNION ALL
SELECT 'technical_calls' AS table_name, 'call_id' AS column_name, 'STRING' AS data_type, 1 AS column_position,
  true AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^C[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^C[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `call_id` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `call_id`)) AS top_values
FROM (SELECT `call_id` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'customer_id' AS column_name, 'STRING' AS data_type, 2 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^CU[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^CU[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `customer_id` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `customer_id`)) AS top_values
FROM (SELECT `customer_id` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'call_date' AS column_name, 'DATE' AS data_type, 3 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'not in the future' AS domain_rule,
  count_if(c > current_date()) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `call_date` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `call_date`)) AS top_values
FROM (SELECT `call_date` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'call_month' AS column_name, 'DATE' AS data_type, 4 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'equals first day of call_date month' AS domain_rule,
  count_if(c <> trunc(call_date, 'MM')) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `call_month` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `call_month`)) AS top_values
FROM (SELECT `call_month` AS c, call_date FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'region' AS column_name, 'STRING' AS data_type, 5 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `region` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `region`)) AS top_values
FROM (SELECT `region` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'platform' AS column_name, 'STRING' AS data_type, 6 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `platform` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `platform`)) AS top_values
FROM (SELECT `platform` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'product' AS column_name, 'STRING' AS data_type, 7 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `product` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `product`)) AS top_values
FROM (SELECT `product` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'customer_segment' AS column_name, 'STRING' AS data_type, 8 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `customer_segment` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `customer_segment`)) AS top_values
FROM (SELECT `customer_segment` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'channel' AS column_name, 'STRING' AS data_type, 9 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `channel` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `channel`)) AS top_values
FROM (SELECT `channel` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'issue_type' AS column_name, 'STRING' AS data_type, 10 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `issue_type` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `issue_type`)) AS top_values
FROM (SELECT `issue_type` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'repeat_contact_flag' AS column_name, 'INT' AS data_type, 11 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  round(avg(c), 2) AS avg_value,
  CAST(percentile_approx(c, 0.5) AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'value IN (0,1)' AS domain_rule,
  count_if(c NOT IN (0,1)) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `repeat_contact_flag` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `repeat_contact_flag`)) AS top_values
FROM (SELECT `repeat_contact_flag` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'call_duration_minutes' AS column_name, 'INT' AS data_type, 12 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  round(avg(c), 2) AS avg_value,
  CAST(percentile_approx(c, 0.5) AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  '1 <= value <= 240' AS domain_rule,
  count_if(c < 1 OR c > 240) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `call_duration_minutes` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `call_duration_minutes`)) AS top_values
FROM (SELECT `call_duration_minutes` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'resolution_status' AS column_name, 'STRING' AS data_type, 13 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `resolution_status` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `resolution_status`)) AS top_values
FROM (SELECT `resolution_status` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'customer_sentiment' AS column_name, 'STRING' AS data_type, 14 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `customer_sentiment` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `customer_sentiment`)) AS top_values
FROM (SELECT `customer_sentiment` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'technical_calls' AS table_name, 'agent_id' AS column_name, 'STRING' AS data_type, 15 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^A[0-9]+$' AS domain_rule,
  count_if(NOT c RLIKE '^A[0-9]+$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `agent_id` AS v, count(*) AS n FROM workspace.xplore.technical_calls GROUP BY `agent_id`)) AS top_values
FROM (SELECT `agent_id` AS c FROM workspace.xplore.technical_calls)
UNION ALL
SELECT 'transcripts' AS table_name, 'call_id' AS column_name, 'STRING' AS data_type, 1 AS column_position,
  true AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^C[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^C[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `call_id` AS v, count(*) AS n FROM workspace.xplore.transcripts GROUP BY `call_id`)) AS top_values
FROM (SELECT `call_id` AS c FROM workspace.xplore.transcripts)
UNION ALL
SELECT 'transcripts' AS table_name, 'transcript_id' AS column_name, 'STRING' AS data_type, 2 AS column_position,
  true AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^T[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^T[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `transcript_id` AS v, count(*) AS n FROM workspace.xplore.transcripts GROUP BY `transcript_id`)) AS top_values
FROM (SELECT `transcript_id` AS c FROM workspace.xplore.transcripts)
UNION ALL
SELECT 'transcripts' AS table_name, 'transcript_text' AS column_name, 'STRING' AS data_type, 3 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `transcript_text` AS v, count(*) AS n FROM workspace.xplore.transcripts GROUP BY `transcript_text`)) AS top_values
FROM (SELECT `transcript_text` AS c FROM workspace.xplore.transcripts)
UNION ALL
SELECT 'transcripts' AS table_name, 'detected_theme' AS column_name, 'STRING' AS data_type, 4 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `detected_theme` AS v, count(*) AS n FROM workspace.xplore.transcripts GROUP BY `detected_theme`)) AS top_values
FROM (SELECT `detected_theme` AS c FROM workspace.xplore.transcripts)
UNION ALL
SELECT 'transcripts' AS table_name, 'ai_sentiment' AS column_name, 'STRING' AS data_type, 5 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `ai_sentiment` AS v, count(*) AS n FROM workspace.xplore.transcripts GROUP BY `ai_sentiment`)) AS top_values
FROM (SELECT `ai_sentiment` AS c FROM workspace.xplore.transcripts)
UNION ALL
SELECT 'transcripts' AS table_name, 'ai_summary' AS column_name, 'STRING' AS data_type, 6 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `ai_summary` AS v, count(*) AS n FROM workspace.xplore.transcripts GROUP BY `ai_summary`)) AS top_values
FROM (SELECT `ai_summary` AS c FROM workspace.xplore.transcripts)
UNION ALL
SELECT 'transcripts' AS table_name, 'transcript_language' AS column_name, 'STRING' AS data_type, 7 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `transcript_language` AS v, count(*) AS n FROM workspace.xplore.transcripts GROUP BY `transcript_language`)) AS top_values
FROM (SELECT `transcript_language` AS c FROM workspace.xplore.transcripts)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'feedback_id' AS column_name, 'STRING' AS data_type, 1 AS column_position,
  true AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^F[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^F[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `feedback_id` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `feedback_id`)) AS top_values
FROM (SELECT `feedback_id` AS c FROM workspace.xplore.voc_feedback)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'customer_id' AS column_name, 'STRING' AS data_type, 2 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^CU[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^CU[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `customer_id` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `customer_id`)) AS top_values
FROM (SELECT `customer_id` AS c FROM workspace.xplore.voc_feedback)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'call_id' AS column_name, 'STRING' AS data_type, 3 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  'matches ^C[0-9]{5}$' AS domain_rule,
  count_if(NOT c RLIKE '^C[0-9]{5}$') AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `call_id` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `call_id`)) AS top_values
FROM (SELECT `call_id` AS c FROM workspace.xplore.voc_feedback)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'feedback_date' AS column_name, 'DATE' AS data_type, 4 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  'not in the future' AS domain_rule,
  count_if(c > current_date()) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `feedback_date` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `feedback_date`)) AS top_values
FROM (SELECT `feedback_date` AS c FROM workspace.xplore.voc_feedback)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'csat_score_1_to_5' AS column_name, 'INT' AS data_type, 5 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  0 AS blank_count,
  count(DISTINCT c) AS distinct_count,
  0 AS case_or_space_variants,
  CAST(min(c) AS STRING) AS min_value,
  CAST(max(c) AS STRING) AS max_value,
  round(avg(c), 2) AS avg_value,
  CAST(percentile_approx(c, 0.5) AS DOUBLE) AS median_value,
  CAST(NULL AS DOUBLE) AS avg_length,
  '1 <= value <= 5' AS domain_rule,
  count_if(c < 1 OR c > 5) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `csat_score_1_to_5` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `csat_score_1_to_5`)) AS top_values
FROM (SELECT `csat_score_1_to_5` AS c FROM workspace.xplore.voc_feedback)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'nps_group' AS column_name, 'STRING' AS data_type, 6 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `nps_group` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `nps_group`)) AS top_values
FROM (SELECT `nps_group` AS c FROM workspace.xplore.voc_feedback)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'feedback_topic' AS column_name, 'STRING' AS data_type, 7 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `feedback_topic` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `feedback_topic`)) AS top_values
FROM (SELECT `feedback_topic` AS c FROM workspace.xplore.voc_feedback)
UNION ALL
SELECT 'voc_feedback' AS table_name, 'verbatim_comment' AS column_name, 'STRING' AS data_type, 8 AS column_position,
  false AS expected_unique,
  count(*) AS row_count,
  count_if(c IS NULL) AS null_count,
  count_if(trim(c) = '') AS blank_count,
  count(DISTINCT c) AS distinct_count,
  count(DISTINCT c) - count(DISTINCT lower(trim(c))) AS case_or_space_variants,
  CAST(NULL AS STRING) AS min_value,
  CAST(NULL AS STRING) AS max_value,
  CAST(NULL AS DOUBLE) AS avg_value,
  CAST(NULL AS DOUBLE) AS median_value,
  round(avg(length(c)), 1) AS avg_length,
  CAST(NULL AS STRING) AS domain_rule,
  CAST(NULL AS BIGINT) AS domain_violations,
  (SELECT concat_ws(' | ', transform(slice(sort_array(collect_list(named_struct('k', -n, 'v',
      concat(left(coalesce(CAST(v AS STRING), '<NULL>'), 40), ' (', CAST(n AS STRING), ')')))), 1, 5), x -> x.v))
   FROM (SELECT `verbatim_comment` AS v, count(*) AS n FROM workspace.xplore.voc_feedback GROUP BY `verbatim_comment`)) AS top_values
FROM (SELECT `verbatim_comment` AS c FROM workspace.xplore.voc_feedback)
)
SELECT
  table_name, column_name, data_type, column_position, expected_unique,
  row_count, null_count, round(100 * null_count / row_count, 1) AS null_pct, blank_count,
  distinct_count, round(100 * distinct_count / row_count, 1) AS distinct_pct,
  CASE WHEN expected_unique THEN row_count - null_count - distinct_count END AS duplicate_key_rows,
  case_or_space_variants, min_value, max_value, avg_value, median_value, avg_length,
  domain_rule, domain_violations, top_values,
  CASE
    WHEN null_count = row_count
      OR (expected_unique AND row_count - null_count - distinct_count > 0)
      OR coalesce(domain_violations, 0) > 0                          THEN 'FAIL'
    WHEN null_count > 0 OR blank_count > 0 OR case_or_space_variants > 0
      OR distinct_count = 1                                          THEN 'WARN'
    ELSE 'OK'
  END AS health_status,
  concat_ws('; ',
    CASE WHEN null_count = row_count THEN 'all values null' END,
    CASE WHEN null_count > 0 AND null_count < row_count THEN concat(null_count, ' nulls') END,
    CASE WHEN blank_count > 0 THEN concat(blank_count, ' blank strings') END,
    CASE WHEN expected_unique AND row_count - null_count - distinct_count > 0
         THEN concat(row_count - null_count - distinct_count, ' duplicate key rows') END,
    CASE WHEN case_or_space_variants > 0 THEN concat(case_or_space_variants, ' case/space variants') END,
    CASE WHEN distinct_count = 1 THEN 'constant value' END,
    CASE WHEN domain_violations > 0 THEN concat(domain_violations, ' rows break rule: ', domain_rule) END
  ) AS issues,
  current_timestamp() AS snapshot_at
FROM stats;

-- View: problems first
SELECT table_name, column_name, health_status, issues, null_pct, distinct_count, top_values
FROM workspace.xplore.dq_column_health
ORDER BY CASE health_status WHEN 'FAIL' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END, table_name, column_position;
