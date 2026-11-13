-- Copyright 2026 MNC Labs, Inc. Licensed under Apache 2.0.
-- Author: Asaad Riaz
--
-- Banking reference integration seed data.
-- Creates the schema and populates all 13 scenarios.

-- ============================================================================
-- Schema
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_events (
    id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    scenario TEXT NOT NULL,
    event_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    field_affected TEXT,
    old_value TEXT,
    new_value TEXT,
    active BOOLEAN NOT NULL DEFAULT true,
    timestamp TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_state (
    id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    scenario TEXT NOT NULL,
    field TEXT NOT NULL,
    value INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    source_version TEXT
);

CREATE TABLE IF NOT EXISTS source_versions (
    model TEXT NOT NULL,
    scenario TEXT NOT NULL,
    field TEXT NOT NULL,
    version TEXT NOT NULL,
    minimum_required TEXT NOT NULL,
    PRIMARY KEY (model, scenario, field)
);

CREATE TABLE IF NOT EXISTS adjustment_coverage (
    model TEXT NOT NULL,
    scenario TEXT NOT NULL,
    category TEXT NOT NULL,
    label TEXT NOT NULL,
    expected INTEGER NOT NULL,
    captured INTEGER NOT NULL,
    PRIMARY KEY (model, scenario, category)
);

CREATE TABLE IF NOT EXISTS missing_adjustments (
    id SERIAL PRIMARY KEY,
    model TEXT NOT NULL,
    scenario TEXT NOT NULL,
    entity TEXT NOT NULL,
    adjustment_type TEXT NOT NULL,
    impact TEXT NOT NULL,
    classification TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS certification_scope (
    model TEXT NOT NULL,
    scenario TEXT NOT NULL,
    operational_domain TEXT NOT NULL,
    corridor TEXT,
    certification_window TEXT NOT NULL,
    transactions_in_scope BIGINT,
    modifications_evaluated BIGINT,
    PRIMARY KEY (model, scenario)
);

-- ============================================================================
-- Certification Scope
-- ============================================================================

-- SWIFT scenarios share a single scope definition
INSERT INTO certification_scope (model, scenario, operational_domain, corridor, certification_window, transactions_in_scope, modifications_evaluated) VALUES
    ('swift', 'S1', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000),
    ('swift', 'S2', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000),
    ('swift', 'S3', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000),
    ('swift', 'S4', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000),
    ('swift', 'S5', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000),
    ('swift', 'S6', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000),
    ('swift', 'S7', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000),
    ('swift', 'S8', 'Cross-Border Wire Transfers (SWIFT MT103/MT202)', 'USD/EUR/GBP Multi-Corridor', 'Q4 2025 (Oct 1 - Dec 31)', 2400000, 11000000);

-- Balance Sheet scenarios
INSERT INTO certification_scope (model, scenario, operational_domain, corridor, certification_window, transactions_in_scope, modifications_evaluated) VALUES
    ('balance_sheet', 'BS1', 'Multi-Entity Balance Sheet Consolidation', NULL, 'Q4 2025 (Oct 1 - Dec 31)', 41228, NULL),
    ('balance_sheet', 'BS2', 'Multi-Entity Balance Sheet Consolidation', NULL, 'Q4 2025 (Oct 1 - Dec 31)', 41228, NULL),
    ('balance_sheet', 'BS3', 'Multi-Entity Balance Sheet Consolidation', NULL, 'Q4 2025 (Oct 1 - Dec 31)', 41228, NULL),
    ('balance_sheet', 'BS4', 'Multi-Entity Balance Sheet Consolidation', NULL, 'Q4 2025 (Oct 1 - Dec 31)', 41228, NULL),
    ('balance_sheet', 'BS5', 'Multi-Entity Balance Sheet Consolidation', NULL, 'Q4 2025 (Oct 1 - Dec 31)', 41228, NULL);


-- ============================================================================
-- SWIFT Operational Events
-- ============================================================================

-- Helper: insert a full set of 7 SWIFT events for a scenario.
-- Events are identical across SWIFT scenarios; only the active flag differs.

-- S1: All events active (clean certification)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S1-001', 'swift', 'S1', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T08:01:12Z'),
    ('swift-S1-002', 'swift', 'S1', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T08:01:14Z'),
    ('swift-S1-003', 'swift', 'S1', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T08:01:15Z'),
    ('swift-S1-004', 'swift', 'S1', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T08:02:30Z'),
    ('swift-S1-005', 'swift', 'S1', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', true,  '2025-12-15T08:02:45Z'),
    ('swift-S1-006', 'swift', 'S1', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', true,  '2025-12-15T08:03:10Z'),
    ('swift-S1-007', 'swift', 'S1', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T08:04:00Z');

-- S2: EVT-005 suppressed (enrichment missing → cascade)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S2-001', 'swift', 'S2', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T09:01:12Z'),
    ('swift-S2-002', 'swift', 'S2', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T09:01:14Z'),
    ('swift-S2-003', 'swift', 'S2', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T09:01:15Z'),
    ('swift-S2-004', 'swift', 'S2', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T09:02:30Z'),
    ('swift-S2-005', 'swift', 'S2', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', false, '2025-12-15T09:02:45Z'),
    ('swift-S2-006', 'swift', 'S2', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', true,  '2025-12-15T09:03:10Z'),
    ('swift-S2-007', 'swift', 'S2', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T09:04:00Z');

-- S3: All events active (prohibition injection handled by demo.py)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S3-001', 'swift', 'S3', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T10:01:12Z'),
    ('swift-S3-002', 'swift', 'S3', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T10:01:14Z'),
    ('swift-S3-003', 'swift', 'S3', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T10:01:15Z'),
    ('swift-S3-004', 'swift', 'S3', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T10:02:30Z'),
    ('swift-S3-005', 'swift', 'S3', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', true,  '2025-12-15T10:02:45Z'),
    ('swift-S3-006', 'swift', 'S3', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', true,  '2025-12-15T10:03:10Z'),
    ('swift-S3-007', 'swift', 'S3', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T10:04:00Z');

-- S4: All events active (admissibility — source version downgrade in source_versions table)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S4-001', 'swift', 'S4', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T11:01:12Z'),
    ('swift-S4-002', 'swift', 'S4', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T11:01:14Z'),
    ('swift-S4-003', 'swift', 'S4', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T11:01:15Z'),
    ('swift-S4-004', 'swift', 'S4', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T11:02:30Z'),
    ('swift-S4-005', 'swift', 'S4', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', true,  '2025-12-15T11:02:45Z'),
    ('swift-S4-006', 'swift', 'S4', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', true,  '2025-12-15T11:03:10Z'),
    ('swift-S4-007', 'swift', 'S4', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T11:04:00Z');

-- S5: EVT-005 suppressed + admissibility downgrade + prohibition (handled by demo.py)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S5-001', 'swift', 'S5', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T12:01:12Z'),
    ('swift-S5-002', 'swift', 'S5', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T12:01:14Z'),
    ('swift-S5-003', 'swift', 'S5', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T12:01:15Z'),
    ('swift-S5-004', 'swift', 'S5', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T12:02:30Z'),
    ('swift-S5-005', 'swift', 'S5', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', false, '2025-12-15T12:02:45Z'),
    ('swift-S5-006', 'swift', 'S5', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', true,  '2025-12-15T12:03:10Z'),
    ('swift-S5-007', 'swift', 'S5', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T12:04:00Z');

-- S6: EVT-006 suppressed (dual authorization missing)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S6-001', 'swift', 'S6', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T13:01:12Z'),
    ('swift-S6-002', 'swift', 'S6', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T13:01:14Z'),
    ('swift-S6-003', 'swift', 'S6', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T13:01:15Z'),
    ('swift-S6-004', 'swift', 'S6', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T13:02:30Z'),
    ('swift-S6-005', 'swift', 'S6', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', true,  '2025-12-15T13:02:45Z'),
    ('swift-S6-006', 'swift', 'S6', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', false, '2025-12-15T13:03:10Z'),
    ('swift-S6-007', 'swift', 'S6', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T13:04:00Z');

-- S7: All events active (compliance admissibility — source version in source_versions table)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S7-001', 'swift', 'S7', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T14:01:12Z'),
    ('swift-S7-002', 'swift', 'S7', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T14:01:14Z'),
    ('swift-S7-003', 'swift', 'S7', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T14:01:15Z'),
    ('swift-S7-004', 'swift', 'S7', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T14:02:30Z'),
    ('swift-S7-005', 'swift', 'S7', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', true,  '2025-12-15T14:02:45Z'),
    ('swift-S7-006', 'swift', 'S7', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', true,  '2025-12-15T14:03:10Z'),
    ('swift-S7-007', 'swift', 'S7', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T14:04:00Z');

-- S8: EVT-005 suppressed (boundary evolution — same evidence as S2, evaluated against v1.0/v1.2/v1.4)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('swift-S8-001', 'swift', 'S8', 'EVT-001', 'origination',    'validation',    'SWIFT MT103 origination validated against Alliance Gateway',                   'originating_swift_valid',          NULL, '1', true,  '2025-12-15T15:01:12Z'),
    ('swift-S8-002', 'swift', 'S8', 'EVT-002', 'verification',   'validation',    'Beneficiary account verified against Core Banking account master',              'beneficiary_account_verified',     NULL, '1', true,  '2025-12-15T15:01:14Z'),
    ('swift-S8-003', 'swift', 'S8', 'EVT-003', 'compliance',     'screening',     'Compliance screening passed through sanctions and PEP checks',                  'compliance_screening_passed',      NULL, '1', true,  '2025-12-15T15:01:15Z'),
    ('swift-S8-004', 'swift', 'S8', 'EVT-004', 'correction',     'manual',        'Human correction logged — beneficiary name standardization',                    'human_correction_logged',          'J. Smith', 'John Smith', true, '2025-12-15T15:02:30Z'),
    ('swift-S8-005', 'swift', 'S8', 'EVT-005', 'enrichment',     'system',        'System auto-enrichment applied — intermediary BIC and charge codes',            'system_enrichment_logged',         NULL, '1', false, '2025-12-15T15:02:45Z'),
    ('swift-S8-006', 'swift', 'S8', 'EVT-006', 'authorization',  'approval',      'Dual authorization completed — maker/checker for value > $50K',                 'dual_authorization_completed',     NULL, '1', true,  '2025-12-15T15:03:10Z'),
    ('swift-S8-007', 'swift', 'S8', 'EVT-007', 'reconciliation', 'verification',  'Reconciliation against source completed — nostro projected balance confirmed',  'reconciliation_against_source',    NULL, '1', true,  '2025-12-15T15:04:00Z');


-- ============================================================================
-- Balance Sheet Operational Events
-- ============================================================================

-- BS1: All events active (clean certification)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('bs-BS1-001', 'balance_sheet', 'BS1', 'BS-EVT-001', 'collection',     'receipt',         'Subsidiary data received from all reporting entities',                      'all_subsidiary_data_received',             NULL, '1', true,  '2025-12-15T06:00:00Z'),
    ('bs-BS1-002', 'balance_sheet', 'BS1', 'BS-EVT-002', 'classification', 'classification',  'All adjustment events classified as financial or operational',              'adjustment_events_classified',             NULL, '1', true,  '2025-12-15T06:15:00Z'),
    ('bs-BS1-003', 'balance_sheet', 'BS1', 'BS-EVT-003', 'capture',        'collection',      'Non-financial adjustments captured from operational tracking systems',      'non_financial_adjustments_captured',       NULL, '1', true,  '2025-12-15T06:30:00Z'),
    ('bs-BS1-004', 'balance_sheet', 'BS1', 'BS-EVT-004', 'reconciliation', 'verification',    'Reconciliation variance within materiality threshold',                      'reconciliation_variance_within_threshold', NULL, '1', true,  '2025-12-15T07:00:00Z'),
    ('bs-BS1-005', 'balance_sheet', 'BS1', 'BS-EVT-005', 'verification',   'verification',    'Data lineage verified from source through consolidation',                   'data_lineage_verified',                   NULL, '1', true,  '2025-12-15T07:30:00Z'),
    ('bs-BS1-006', 'balance_sheet', 'BS1', 'BS-EVT-006', 'certification',  'approval',        'Certifier sign-off obtained for consolidation window',                      'certifier_sign_off_obtained',             NULL, '1', true,  '2025-12-15T08:00:00Z');

-- BS2: All events active, but 5 missing operational adjustments (non_financial_adjustments_captured = 0)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('bs-BS2-001', 'balance_sheet', 'BS2', 'BS-EVT-001', 'collection',     'receipt',         'Subsidiary data received from all reporting entities',                      'all_subsidiary_data_received',             NULL, '1', true,  '2025-12-15T06:00:00Z'),
    ('bs-BS2-002', 'balance_sheet', 'BS2', 'BS-EVT-002', 'classification', 'classification',  'All adjustment events classified as financial or operational',              'adjustment_events_classified',             NULL, '1', true,  '2025-12-15T06:15:00Z'),
    ('bs-BS2-003', 'balance_sheet', 'BS2', 'BS-EVT-003', 'capture',        'collection',      'Non-financial adjustments captured from operational tracking systems',      'non_financial_adjustments_captured',       NULL, '0', true,  '2025-12-15T06:30:00Z'),
    ('bs-BS2-004', 'balance_sheet', 'BS2', 'BS-EVT-004', 'reconciliation', 'verification',    'Reconciliation variance within materiality threshold',                      'reconciliation_variance_within_threshold', NULL, '1', true,  '2025-12-15T07:00:00Z'),
    ('bs-BS2-005', 'balance_sheet', 'BS2', 'BS-EVT-005', 'verification',   'verification',    'Data lineage verified from source through consolidation',                   'data_lineage_verified',                   NULL, '1', true,  '2025-12-15T07:30:00Z'),
    ('bs-BS2-006', 'balance_sheet', 'BS2', 'BS-EVT-006', 'certification',  'approval',        'Certifier sign-off obtained for consolidation window',                      'certifier_sign_off_obtained',             NULL, '1', true,  '2025-12-15T08:00:00Z');

-- BS3: Same as BS2 (missing adjustments + prohibition injection handled by demo.py)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('bs-BS3-001', 'balance_sheet', 'BS3', 'BS-EVT-001', 'collection',     'receipt',         'Subsidiary data received from all reporting entities',                      'all_subsidiary_data_received',             NULL, '1', true,  '2025-12-15T06:00:00Z'),
    ('bs-BS3-002', 'balance_sheet', 'BS3', 'BS-EVT-002', 'classification', 'classification',  'All adjustment events classified as financial or operational',              'adjustment_events_classified',             NULL, '1', true,  '2025-12-15T06:15:00Z'),
    ('bs-BS3-003', 'balance_sheet', 'BS3', 'BS-EVT-003', 'capture',        'collection',      'Non-financial adjustments captured from operational tracking systems',      'non_financial_adjustments_captured',       NULL, '0', true,  '2025-12-15T06:30:00Z'),
    ('bs-BS3-004', 'balance_sheet', 'BS3', 'BS-EVT-004', 'reconciliation', 'verification',    'Reconciliation variance within materiality threshold',                      'reconciliation_variance_within_threshold', NULL, '1', true,  '2025-12-15T07:00:00Z'),
    ('bs-BS3-005', 'balance_sheet', 'BS3', 'BS-EVT-005', 'verification',   'verification',    'Data lineage verified from source through consolidation',                   'data_lineage_verified',                   NULL, '1', true,  '2025-12-15T07:30:00Z'),
    ('bs-BS3-006', 'balance_sheet', 'BS3', 'BS-EVT-006', 'certification',  'approval',        'Certifier sign-off obtained for consolidation window',                      'certifier_sign_off_obtained',             NULL, '1', true,  '2025-12-15T08:00:00Z');

-- BS4: Boundary evolution — non_financial + data_lineage = 0 (v0.9 passes without them, v1.0 fails)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('bs-BS4-001', 'balance_sheet', 'BS4', 'BS-EVT-001', 'collection',     'receipt',         'Subsidiary data received from all reporting entities',                      'all_subsidiary_data_received',             NULL, '1', true,  '2025-12-15T06:00:00Z'),
    ('bs-BS4-002', 'balance_sheet', 'BS4', 'BS-EVT-002', 'classification', 'classification',  'All adjustment events classified as financial or operational',              'adjustment_events_classified',             NULL, '1', true,  '2025-12-15T06:15:00Z'),
    ('bs-BS4-003', 'balance_sheet', 'BS4', 'BS-EVT-003', 'capture',        'collection',      'Non-financial adjustments captured from operational tracking systems',      'non_financial_adjustments_captured',       NULL, '0', true,  '2025-12-15T06:30:00Z'),
    ('bs-BS4-004', 'balance_sheet', 'BS4', 'BS-EVT-004', 'reconciliation', 'verification',    'Reconciliation variance within materiality threshold',                      'reconciliation_variance_within_threshold', NULL, '1', true,  '2025-12-15T07:00:00Z'),
    ('bs-BS4-005', 'balance_sheet', 'BS4', 'BS-EVT-005', 'verification',   'verification',    'Data lineage verified from source through consolidation',                   'data_lineage_verified',                   NULL, '0', true,  '2025-12-15T07:30:00Z'),
    ('bs-BS4-006', 'balance_sheet', 'BS4', 'BS-EVT-006', 'certification',  'approval',        'Certifier sign-off obtained for consolidation window',                      'certifier_sign_off_obtained',             NULL, '1', true,  '2025-12-15T08:00:00Z');

-- BS5: BS-EVT-003 produces 0 (non-financial adjustments not captured — operational gap)
INSERT INTO operational_events (id, model, scenario, event_id, stage, event_type, description, field_affected, old_value, new_value, active, timestamp) VALUES
    ('bs-BS5-001', 'balance_sheet', 'BS5', 'BS-EVT-001', 'collection',     'receipt',         'Subsidiary data received from all reporting entities',                      'all_subsidiary_data_received',             NULL, '1', true,  '2025-12-15T06:00:00Z'),
    ('bs-BS5-002', 'balance_sheet', 'BS5', 'BS-EVT-002', 'classification', 'classification',  'All adjustment events classified as financial or operational',              'adjustment_events_classified',             NULL, '1', true,  '2025-12-15T06:15:00Z'),
    ('bs-BS5-003', 'balance_sheet', 'BS5', 'BS-EVT-003', 'capture',        'collection',      'Non-financial adjustments captured from operational tracking systems',      'non_financial_adjustments_captured',       NULL, '0', false, '2025-12-15T06:30:00Z'),
    ('bs-BS5-004', 'balance_sheet', 'BS5', 'BS-EVT-004', 'reconciliation', 'verification',    'Reconciliation variance within materiality threshold',                      'reconciliation_variance_within_threshold', NULL, '1', true,  '2025-12-15T07:00:00Z'),
    ('bs-BS5-005', 'balance_sheet', 'BS5', 'BS-EVT-005', 'verification',   'verification',    'Data lineage verified from source through consolidation',                   'data_lineage_verified',                   NULL, '1', true,  '2025-12-15T07:30:00Z'),
    ('bs-BS5-006', 'balance_sheet', 'BS5', 'BS-EVT-006', 'certification',  'approval',        'Certifier sign-off obtained for consolidation window',                      'certifier_sign_off_obtained',             NULL, '1', true,  '2025-12-15T08:00:00Z');


-- ============================================================================
-- SWIFT Evidence State
-- ============================================================================

-- S1: All 10 fields = 1, compliant source versions
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S1-ev-01', 'swift', 'S1', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S1-ev-02', 'swift', 'S1', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S1-ev-03', 'swift', 'S1', 'compliance_screening_passed',      1, 'compliance_engine',   '4.0'),
    ('swift-S1-ev-04', 'swift', 'S1', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S1-ev-05', 'swift', 'S1', 'system_enrichment_logged',         1, 'enrichment_service',  NULL),
    ('swift-S1-ev-06', 'swift', 'S1', 'adjustment_classification_complete', 1, 'classification_engine', NULL),
    ('swift-S1-ev-07', 'swift', 'S1', 'all_modification_events_captured', 1, 'event_capture',       NULL),
    ('swift-S1-ev-08', 'swift', 'S1', 'dual_authorization_completed',     1, 'auth_system',         NULL),
    ('swift-S1-ev-09', 'swift', 'S1', 'reconciliation_against_source',    1, 'recon_engine',        '2.3'),
    ('swift-S1-ev-10', 'swift', 'S1', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);

-- S2: EVT-005 suppressed → enrichment/classification/events = 0
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S2-ev-01', 'swift', 'S2', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S2-ev-02', 'swift', 'S2', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S2-ev-03', 'swift', 'S2', 'compliance_screening_passed',      1, 'compliance_engine',   '4.0'),
    ('swift-S2-ev-04', 'swift', 'S2', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S2-ev-05', 'swift', 'S2', 'system_enrichment_logged',         0, 'enrichment_service',  NULL),
    ('swift-S2-ev-06', 'swift', 'S2', 'adjustment_classification_complete', 0, 'classification_engine', NULL),
    ('swift-S2-ev-07', 'swift', 'S2', 'all_modification_events_captured', 0, 'event_capture',       NULL),
    ('swift-S2-ev-08', 'swift', 'S2', 'dual_authorization_completed',     1, 'auth_system',         NULL),
    ('swift-S2-ev-09', 'swift', 'S2', 'reconciliation_against_source',    1, 'recon_engine',        '2.3'),
    ('swift-S2-ev-10', 'swift', 'S2', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);

-- S3: All 10 fields = 1 (prohibition injection is runtime, not DB)
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S3-ev-01', 'swift', 'S3', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S3-ev-02', 'swift', 'S3', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S3-ev-03', 'swift', 'S3', 'compliance_screening_passed',      1, 'compliance_engine',   '4.0'),
    ('swift-S3-ev-04', 'swift', 'S3', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S3-ev-05', 'swift', 'S3', 'system_enrichment_logged',         1, 'enrichment_service',  NULL),
    ('swift-S3-ev-06', 'swift', 'S3', 'adjustment_classification_complete', 1, 'classification_engine', NULL),
    ('swift-S3-ev-07', 'swift', 'S3', 'all_modification_events_captured', 1, 'event_capture',       NULL),
    ('swift-S3-ev-08', 'swift', 'S3', 'dual_authorization_completed',     1, 'auth_system',         NULL),
    ('swift-S3-ev-09', 'swift', 'S3', 'reconciliation_against_source',    1, 'recon_engine',        '2.3'),
    ('swift-S3-ev-10', 'swift', 'S3', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);

-- S4: All 10 fields = 1, but recon source version downgraded to 2.1
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S4-ev-01', 'swift', 'S4', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S4-ev-02', 'swift', 'S4', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S4-ev-03', 'swift', 'S4', 'compliance_screening_passed',      1, 'compliance_engine',   '4.0'),
    ('swift-S4-ev-04', 'swift', 'S4', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S4-ev-05', 'swift', 'S4', 'system_enrichment_logged',         1, 'enrichment_service',  NULL),
    ('swift-S4-ev-06', 'swift', 'S4', 'adjustment_classification_complete', 1, 'classification_engine', NULL),
    ('swift-S4-ev-07', 'swift', 'S4', 'all_modification_events_captured', 1, 'event_capture',       NULL),
    ('swift-S4-ev-08', 'swift', 'S4', 'dual_authorization_completed',     1, 'auth_system',         NULL),
    ('swift-S4-ev-09', 'swift', 'S4', 'reconciliation_against_source',    1, 'recon_engine',        '2.1'),
    ('swift-S4-ev-10', 'swift', 'S4', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);

-- S5: EVT-005 suppressed (3 fields = 0) + recon version downgraded + prohibition at runtime
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S5-ev-01', 'swift', 'S5', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S5-ev-02', 'swift', 'S5', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S5-ev-03', 'swift', 'S5', 'compliance_screening_passed',      1, 'compliance_engine',   '4.0'),
    ('swift-S5-ev-04', 'swift', 'S5', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S5-ev-05', 'swift', 'S5', 'system_enrichment_logged',         0, 'enrichment_service',  NULL),
    ('swift-S5-ev-06', 'swift', 'S5', 'adjustment_classification_complete', 0, 'classification_engine', NULL),
    ('swift-S5-ev-07', 'swift', 'S5', 'all_modification_events_captured', 0, 'event_capture',       NULL),
    ('swift-S5-ev-08', 'swift', 'S5', 'dual_authorization_completed',     1, 'auth_system',         NULL),
    ('swift-S5-ev-09', 'swift', 'S5', 'reconciliation_against_source',    1, 'recon_engine',        '2.1'),
    ('swift-S5-ev-10', 'swift', 'S5', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);

-- S6: dual_authorization_completed = 0 (EVT-006 suppressed)
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S6-ev-01', 'swift', 'S6', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S6-ev-02', 'swift', 'S6', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S6-ev-03', 'swift', 'S6', 'compliance_screening_passed',      1, 'compliance_engine',   '4.0'),
    ('swift-S6-ev-04', 'swift', 'S6', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S6-ev-05', 'swift', 'S6', 'system_enrichment_logged',         1, 'enrichment_service',  NULL),
    ('swift-S6-ev-06', 'swift', 'S6', 'adjustment_classification_complete', 1, 'classification_engine', NULL),
    ('swift-S6-ev-07', 'swift', 'S6', 'all_modification_events_captured', 1, 'event_capture',       NULL),
    ('swift-S6-ev-08', 'swift', 'S6', 'dual_authorization_completed',     0, 'auth_system',         NULL),
    ('swift-S6-ev-09', 'swift', 'S6', 'reconciliation_against_source',    1, 'recon_engine',        '2.3'),
    ('swift-S6-ev-10', 'swift', 'S6', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);

-- S7: All 10 fields = 1, but compliance source version downgraded to 3.8
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S7-ev-01', 'swift', 'S7', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S7-ev-02', 'swift', 'S7', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S7-ev-03', 'swift', 'S7', 'compliance_screening_passed',      1, 'compliance_engine',   '3.8'),
    ('swift-S7-ev-04', 'swift', 'S7', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S7-ev-05', 'swift', 'S7', 'system_enrichment_logged',         1, 'enrichment_service',  NULL),
    ('swift-S7-ev-06', 'swift', 'S7', 'adjustment_classification_complete', 1, 'classification_engine', NULL),
    ('swift-S7-ev-07', 'swift', 'S7', 'all_modification_events_captured', 1, 'event_capture',       NULL),
    ('swift-S7-ev-08', 'swift', 'S7', 'dual_authorization_completed',     1, 'auth_system',         NULL),
    ('swift-S7-ev-09', 'swift', 'S7', 'reconciliation_against_source',    1, 'recon_engine',        '2.3'),
    ('swift-S7-ev-10', 'swift', 'S7', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);

-- S8: Same evidence as S2 (EVT-005 suppressed → 3 fields = 0) — boundary evolution scenario
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('swift-S8-ev-01', 'swift', 'S8', 'originating_swift_valid',          1, 'swift_gateway',       NULL),
    ('swift-S8-ev-02', 'swift', 'S8', 'beneficiary_account_verified',     1, 'core_banking',        NULL),
    ('swift-S8-ev-03', 'swift', 'S8', 'compliance_screening_passed',      1, 'compliance_engine',   '4.0'),
    ('swift-S8-ev-04', 'swift', 'S8', 'human_correction_logged',          1, 'ops_workflow',        NULL),
    ('swift-S8-ev-05', 'swift', 'S8', 'system_enrichment_logged',         0, 'enrichment_service',  NULL),
    ('swift-S8-ev-06', 'swift', 'S8', 'adjustment_classification_complete', 0, 'classification_engine', NULL),
    ('swift-S8-ev-07', 'swift', 'S8', 'all_modification_events_captured', 0, 'event_capture',       NULL),
    ('swift-S8-ev-08', 'swift', 'S8', 'dual_authorization_completed',     1, 'auth_system',         NULL),
    ('swift-S8-ev-09', 'swift', 'S8', 'reconciliation_against_source',    1, 'recon_engine',        '2.3'),
    ('swift-S8-ev-10', 'swift', 'S8', 'nostro_balance_confirmed',         1, 'nostro_system',       NULL);


-- ============================================================================
-- Balance Sheet Evidence State
-- ============================================================================

-- BS1: All 8 fields = 1 (clean certification)
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('bs-BS1-ev-01', 'balance_sheet', 'BS1', 'all_subsidiary_data_received',             1, 'subsidiary_reporting', NULL),
    ('bs-BS1-ev-02', 'balance_sheet', 'BS1', 'adjustment_events_classified',             1, 'classification_engine', NULL),
    ('bs-BS1-ev-03', 'balance_sheet', 'BS1', 'non_financial_adjustments_captured',       1, 'nonfin_tracking', NULL),
    ('bs-BS1-ev-04', 'balance_sheet', 'BS1', 'reconciliation_variance_within_threshold', 1, 'recon_engine',        NULL),
    ('bs-BS1-ev-05', 'balance_sheet', 'BS1', 'data_lineage_verified',                   1, 'lineage_service',     NULL),
    ('bs-BS1-ev-06', 'balance_sheet', 'BS1', 'certifier_sign_off_obtained',             1, 'certifier_workflow',  NULL),
    ('bs-BS1-ev-07', 'balance_sheet', 'BS1', 'intercompany_eliminations_verified',      1, 'intercompany_system', NULL),
    ('bs-BS1-ev-08', 'balance_sheet', 'BS1', 'fx_translation_adjustments_applied',      1, 'fx_translation',      NULL);

-- BS2: non_financial_adjustments_captured = 0 (5 missing operational adjustments)
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('bs-BS2-ev-01', 'balance_sheet', 'BS2', 'all_subsidiary_data_received',             1, 'subsidiary_reporting', NULL),
    ('bs-BS2-ev-02', 'balance_sheet', 'BS2', 'adjustment_events_classified',             1, 'classification_engine', NULL),
    ('bs-BS2-ev-03', 'balance_sheet', 'BS2', 'non_financial_adjustments_captured',       0, 'nonfin_tracking', NULL),
    ('bs-BS2-ev-04', 'balance_sheet', 'BS2', 'reconciliation_variance_within_threshold', 1, 'recon_engine',        NULL),
    ('bs-BS2-ev-05', 'balance_sheet', 'BS2', 'data_lineage_verified',                   1, 'lineage_service',     NULL),
    ('bs-BS2-ev-06', 'balance_sheet', 'BS2', 'certifier_sign_off_obtained',             1, 'certifier_workflow',  NULL),
    ('bs-BS2-ev-07', 'balance_sheet', 'BS2', 'intercompany_eliminations_verified',      1, 'intercompany_system', NULL),
    ('bs-BS2-ev-08', 'balance_sheet', 'BS2', 'fx_translation_adjustments_applied',      1, 'fx_translation',      NULL);

-- BS3: Same evidence as BS2 (prohibition injection is runtime)
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('bs-BS3-ev-01', 'balance_sheet', 'BS3', 'all_subsidiary_data_received',             1, 'subsidiary_reporting', NULL),
    ('bs-BS3-ev-02', 'balance_sheet', 'BS3', 'adjustment_events_classified',             1, 'classification_engine', NULL),
    ('bs-BS3-ev-03', 'balance_sheet', 'BS3', 'non_financial_adjustments_captured',       0, 'nonfin_tracking', NULL),
    ('bs-BS3-ev-04', 'balance_sheet', 'BS3', 'reconciliation_variance_within_threshold', 1, 'recon_engine',        NULL),
    ('bs-BS3-ev-05', 'balance_sheet', 'BS3', 'data_lineage_verified',                   1, 'lineage_service',     NULL),
    ('bs-BS3-ev-06', 'balance_sheet', 'BS3', 'certifier_sign_off_obtained',             1, 'certifier_workflow',  NULL),
    ('bs-BS3-ev-07', 'balance_sheet', 'BS3', 'intercompany_eliminations_verified',      1, 'intercompany_system', NULL),
    ('bs-BS3-ev-08', 'balance_sheet', 'BS3', 'fx_translation_adjustments_applied',      1, 'fx_translation',      NULL);

-- BS4: non_financial = 0, data_lineage = 0 (evolution: v0.9 passes without them, v1.0 fails)
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('bs-BS4-ev-01', 'balance_sheet', 'BS4', 'all_subsidiary_data_received',             1, 'subsidiary_reporting', NULL),
    ('bs-BS4-ev-02', 'balance_sheet', 'BS4', 'adjustment_events_classified',             1, 'classification_engine', NULL),
    ('bs-BS4-ev-03', 'balance_sheet', 'BS4', 'non_financial_adjustments_captured',       0, 'nonfin_tracking', NULL),
    ('bs-BS4-ev-04', 'balance_sheet', 'BS4', 'reconciliation_variance_within_threshold', 1, 'recon_engine',        NULL),
    ('bs-BS4-ev-05', 'balance_sheet', 'BS4', 'data_lineage_verified',                   0, 'lineage_service',     NULL),
    ('bs-BS4-ev-06', 'balance_sheet', 'BS4', 'certifier_sign_off_obtained',             1, 'certifier_workflow',  NULL),
    ('bs-BS4-ev-07', 'balance_sheet', 'BS4', 'intercompany_eliminations_verified',      1, 'intercompany_system', NULL),
    ('bs-BS4-ev-08', 'balance_sheet', 'BS4', 'fx_translation_adjustments_applied',      1, 'fx_translation',      NULL);

-- BS5: non_financial_adjustments_captured = 0 (event BS-EVT-003 suppressed — operational gap)
INSERT INTO evidence_state (id, model, scenario, field, value, source, source_version) VALUES
    ('bs-BS5-ev-01', 'balance_sheet', 'BS5', 'all_subsidiary_data_received',             1, 'subsidiary_reporting', NULL),
    ('bs-BS5-ev-02', 'balance_sheet', 'BS5', 'adjustment_events_classified',             1, 'classification_engine', NULL),
    ('bs-BS5-ev-03', 'balance_sheet', 'BS5', 'non_financial_adjustments_captured',       0, 'nonfin_tracking', NULL),
    ('bs-BS5-ev-04', 'balance_sheet', 'BS5', 'reconciliation_variance_within_threshold', 1, 'recon_engine',        NULL),
    ('bs-BS5-ev-05', 'balance_sheet', 'BS5', 'data_lineage_verified',                   1, 'lineage_service',     NULL),
    ('bs-BS5-ev-06', 'balance_sheet', 'BS5', 'certifier_sign_off_obtained',             1, 'certifier_workflow',  NULL),
    ('bs-BS5-ev-07', 'balance_sheet', 'BS5', 'intercompany_eliminations_verified',      1, 'intercompany_system', NULL),
    ('bs-BS5-ev-08', 'balance_sheet', 'BS5', 'fx_translation_adjustments_applied',      1, 'fx_translation',      NULL);


-- ============================================================================
-- Source Versions (admissibility mutation scenarios)
-- ============================================================================

-- S4: recon_engine downgraded to v2.1 (minimum required 2.3)
INSERT INTO source_versions (model, scenario, field, version, minimum_required) VALUES
    ('swift', 'S4', 'reconciliation_against_source', '2.1', '2.3');

-- S5: recon_engine downgraded to v2.1 (same as S4, plus completeness + prohibition)
INSERT INTO source_versions (model, scenario, field, version, minimum_required) VALUES
    ('swift', 'S5', 'reconciliation_against_source', '2.1', '2.3');

-- S7: compliance_engine downgraded to v3.8 (minimum required 4.0)
INSERT INTO source_versions (model, scenario, field, version, minimum_required) VALUES
    ('swift', 'S7', 'compliance_screening_passed', '3.8', '4.0');


-- ============================================================================
-- Adjustment Coverage (Balance Sheet scenarios)
-- ============================================================================

-- BS1: Full coverage — all adjustments captured
INSERT INTO adjustment_coverage (model, scenario, category, label, expected, captured) VALUES
    ('balance_sheet', 'BS1', 'financial',   'Financial Adjustments',   38109, 38109),
    ('balance_sheet', 'BS1', 'operational', 'Operational Adjustments', 3119,  3119);

-- BS2: 5 missing operational adjustments (99.84% operational coverage)
INSERT INTO adjustment_coverage (model, scenario, category, label, expected, captured) VALUES
    ('balance_sheet', 'BS2', 'financial',   'Financial Adjustments',   38109, 38109),
    ('balance_sheet', 'BS2', 'operational', 'Operational Adjustments', 3119,  3114);

-- BS3: Same coverage gap as BS2 (plus prohibition)
INSERT INTO adjustment_coverage (model, scenario, category, label, expected, captured) VALUES
    ('balance_sheet', 'BS3', 'financial',   'Financial Adjustments',   38109, 38109),
    ('balance_sheet', 'BS3', 'operational', 'Operational Adjustments', 3119,  3114);

-- BS4: Same coverage gap as BS2 (plus lineage — for evolution)
INSERT INTO adjustment_coverage (model, scenario, category, label, expected, captured) VALUES
    ('balance_sheet', 'BS4', 'financial',   'Financial Adjustments',   38109, 38109),
    ('balance_sheet', 'BS4', 'operational', 'Operational Adjustments', 3119,  3114);

-- BS5: Operational gap from non-financial adjustments
INSERT INTO adjustment_coverage (model, scenario, category, label, expected, captured) VALUES
    ('balance_sheet', 'BS5', 'financial',   'Financial Adjustments',   38109, 38109),
    ('balance_sheet', 'BS5', 'operational', 'Operational Adjustments', 3119,  3114);


-- ============================================================================
-- Missing Adjustments (Balance Sheet detail rows)
-- ============================================================================

-- BS2: 5 specific missing operational adjustments
INSERT INTO missing_adjustments (model, scenario, entity, adjustment_type, impact, classification, status) VALUES
    ('balance_sheet', 'BS2', 'Singapore Treasury',    'FX Reclassification', '$2.3M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS2', 'Singapore Treasury',    'Hedge Designation',   '$890K', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS2', 'LATAM Shared Services', 'IC Elimination',      '$4.1M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS2', 'LATAM Shared Services', 'Tax Provision',       '$1.7M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS2', 'LATAM Shared Services', 'Lease Modification',  '$560K', 'Operational', 'Missing - not captured');

-- BS3: Same 5 missing (plus prohibition at runtime)
INSERT INTO missing_adjustments (model, scenario, entity, adjustment_type, impact, classification, status) VALUES
    ('balance_sheet', 'BS3', 'Singapore Treasury',    'FX Reclassification', '$2.3M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS3', 'Singapore Treasury',    'Hedge Designation',   '$890K', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS3', 'LATAM Shared Services', 'IC Elimination',      '$4.1M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS3', 'LATAM Shared Services', 'Tax Provision',       '$1.7M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS3', 'LATAM Shared Services', 'Lease Modification',  '$560K', 'Operational', 'Missing - not captured');

-- BS4: Same 5 missing (boundary evolution)
INSERT INTO missing_adjustments (model, scenario, entity, adjustment_type, impact, classification, status) VALUES
    ('balance_sheet', 'BS4', 'Singapore Treasury',    'FX Reclassification', '$2.3M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS4', 'Singapore Treasury',    'Hedge Designation',   '$890K', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS4', 'LATAM Shared Services', 'IC Elimination',      '$4.1M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS4', 'LATAM Shared Services', 'Tax Provision',       '$1.7M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS4', 'LATAM Shared Services', 'Lease Modification',  '$560K', 'Operational', 'Missing - not captured');

-- BS5: Same 5 missing (operational gap)
INSERT INTO missing_adjustments (model, scenario, entity, adjustment_type, impact, classification, status) VALUES
    ('balance_sheet', 'BS5', 'Singapore Treasury',    'FX Reclassification', '$2.3M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS5', 'Singapore Treasury',    'Hedge Designation',   '$890K', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS5', 'LATAM Shared Services', 'IC Elimination',      '$4.1M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS5', 'LATAM Shared Services', 'Tax Provision',       '$1.7M', 'Operational', 'Missing - not captured'),
    ('balance_sheet', 'BS5', 'LATAM Shared Services', 'Lease Modification',  '$560K', 'Operational', 'Missing - not captured');
