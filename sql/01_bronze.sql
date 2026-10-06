-- BRONZE (= dbt sources): the 6 provided CSVs loaded as Delta tables, untouched.
-- Target: workspace.xplore. The CREATE TABLE statements below are the exact ones that were run
-- (recovered from system.query.history on 2026-10-04).

CREATE SCHEMA IF NOT EXISTS workspace.xplore COMMENT 'Bronze: raw assessment data as provided';
CREATE VOLUME IF NOT EXISTS workspace.xplore.raw COMMENT 'Raw CSV files';

-- Upload the CSVs first (from the repository root, in a terminal):
--   databricks fs cp -r Data/ dbfs:/Volumes/workspace/xplore/raw/ -p <profile>

CREATE OR REPLACE TABLE workspace.xplore.technical_calls AS SELECT * EXCEPT (_rescued_data) FROM read_files('/Volumes/workspace/xplore/raw/technical_calls.csv', format => 'csv', header => true, inferSchema => true, multiLine => true, escape => '"');
CREATE OR REPLACE TABLE workspace.xplore.transcripts AS SELECT * EXCEPT (_rescued_data) FROM read_files('/Volumes/workspace/xplore/raw/transcripts.csv', format => 'csv', header => true, inferSchema => true, multiLine => true, escape => '"');
CREATE OR REPLACE TABLE workspace.xplore.voc_feedback AS SELECT * EXCEPT (_rescued_data) FROM read_files('/Volumes/workspace/xplore/raw/voc_feedback.csv', format => 'csv', header => true, inferSchema => true, multiLine => true, escape => '"');
CREATE OR REPLACE TABLE workspace.xplore.call_volume_daily AS SELECT * EXCEPT (_rescued_data) FROM read_files('/Volumes/workspace/xplore/raw/call_volume_daily.csv', format => 'csv', header => true, inferSchema => true, multiLine => true, escape => '"');
CREATE OR REPLACE TABLE workspace.xplore.network_events AS SELECT * EXCEPT (_rescued_data) FROM read_files('/Volumes/workspace/xplore/raw/network_events.csv', format => 'csv', header => true, inferSchema => true, multiLine => true, escape => '"');
CREATE OR REPLACE TABLE workspace.xplore.device_health AS SELECT * EXCEPT (_rescued_data) FROM read_files('/Volumes/workspace/xplore/raw/device_health.csv', format => 'csv', header => true, inferSchema => true, multiLine => true, escape => '"');

-- Check: row counts must equal the CSV line counts minus the header.
SELECT 'technical_calls' AS table_name, count(*) AS row_count FROM workspace.xplore.technical_calls
UNION ALL SELECT 'transcripts', count(*) FROM workspace.xplore.transcripts
UNION ALL SELECT 'voc_feedback', count(*) FROM workspace.xplore.voc_feedback
UNION ALL SELECT 'call_volume_daily', count(*) FROM workspace.xplore.call_volume_daily
UNION ALL SELECT 'network_events', count(*) FROM workspace.xplore.network_events
UNION ALL SELECT 'device_health', count(*) FROM workspace.xplore.device_health;
