-- KI-081: explicit migration only; never run from API or simulator startup.
-- Apply to the verified MOD database after backup and separate deployment approval.
CREATE TABLE IF NOT EXISTS sim_event_outbox_state (
    singleton_id TINYINT PRIMARY KEY,
    stream_id VARCHAR(36) NOT NULL,
    last_sequence BIGINT NOT NULL DEFAULT 0,
    pruned_through BIGINT NOT NULL DEFAULT 0,
    documents BIGINT NOT NULL DEFAULT 0,
    vouchers BIGINT NOT NULL DEFAULT 0,
    integrations BIGINT NOT NULL DEFAULT 0
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS sim_event_outbox (
    sequence BIGINT PRIMARY KEY,
    event_id VARCHAR(128) NOT NULL UNIQUE,
    payload JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    documents BIGINT NOT NULL,
    vouchers BIGINT NOT NULL,
    integrations BIGINT NOT NULL,
    INDEX idx_outbox_created (created_at)
) ENGINE=InnoDB;
INSERT INTO sim_event_outbox_state (singleton_id, stream_id)
SELECT 1, UUID() WHERE NOT EXISTS (SELECT 1 FROM sim_event_outbox_state WHERE singleton_id = 1);
