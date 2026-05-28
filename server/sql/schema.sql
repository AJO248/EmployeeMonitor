-- Prototype schema for EEAM logs
CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id TEXT,
  process_name TEXT,
  window_title TEXT,
  domain TEXT,
  raw JSONB
);

-- Optional timescaledb hypertable conversion (run after installing TimescaleDB)
-- SELECT create_hypertable('events', 'timestamp');
