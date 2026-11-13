# Copyright 2026 MNC Labs, Inc. Licensed under Apache 2.0.
# Author: Asaad Riaz
"""Register the Banking Operational Certification reference template in the VB-OS Cloud template registry.

Creates a multi-boundary template with 5 boundaries, 2 connectors, 2 flows,
and 2 certification models. Users can fork this template to provision the entire
banking certification pipeline with a single click.

Usage:
    python3 seed_template.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import asyncpg

ROOT = Path(__file__).parent


def _resolve_dsn() -> str:
    import os
    import re
    from urllib.parse import quote

    raw = os.environ.get(
        "VBOS_DATABASE_URL", "postgresql://vbos:vbos@localhost:5432/vbos"
    )
    url = raw.replace("postgresql+asyncpg://", "postgresql://")
    m = re.match(r"^(postgresql://[^:]+:)([^@]+)(@.+)$", url)
    if m:
        url = m.group(1) + quote(m.group(2), safe="") + m.group(3)
    return url


DB_DSN = _resolve_dsn()
SLUG = "banking-operational-certification"


def _read_dsl(filename: str) -> str:
    return (ROOT / "boundaries" / filename).read_text()


# ── Evidence schemas ──────────────────────────────────────────────────────

SWIFT_EVIDENCE_SCHEMA = {
    "originating_swift_valid": {"type": "integer"},
    "beneficiary_account_verified": {"type": "integer"},
    "compliance_screening_passed": {"type": "integer"},
    "human_correction_logged": {"type": "integer"},
    "system_enrichment_logged": {"type": "integer"},
    "adjustment_classification_complete": {"type": "integer"},
    "all_modification_events_captured": {"type": "integer"},
    "dual_authorization_completed": {"type": "integer"},
    "reconciliation_against_source": {"type": "integer"},
    "nostro_balance_confirmed": {"type": "integer"},
}

BS_EVIDENCE_SCHEMA = {
    "all_subsidiary_data_received": {"type": "integer"},
    "adjustment_events_classified": {"type": "integer"},
    "non_financial_adjustments_captured": {"type": "integer"},
    "reconciliation_variance_within_threshold": {"type": "integer"},
    "data_lineage_verified": {"type": "integer"},
    "certifier_sign_off_obtained": {"type": "integer"},
    "intercompany_eliminations_verified": {"type": "integer"},
    "fx_translation_adjustments_applied": {"type": "integer"},
}


# ── Boundary set ──────────────────────────────────────────────────────────

BOUNDARY_SET = [
    {
        "ref": "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4",
        "name": "SWIFT Adjustment Integrity (v1.4 — Current)",
        "description": (
            "Current policy: 10 predicates covering origination, verification, "
            "compliance, enrichment, classification, event capture, dual auth, "
            "reconciliation, and nostro confirmation."
        ),
        "dsl_source": _read_dsl("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4.dsl"),
        "evidence_schema": SWIFT_EVIDENCE_SCHEMA,
    },
    {
        "ref": "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2",
        "name": "SWIFT Adjustment Integrity (v1.2)",
        "description": (
            "Interim policy: 8 predicates. Added system_enrichment_logged "
            "requirement over v1.0."
        ),
        "dsl_source": _read_dsl("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2.dsl"),
        "evidence_schema": SWIFT_EVIDENCE_SCHEMA,
    },
    {
        "ref": "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0",
        "name": "SWIFT Adjustment Integrity (v1.0 — Original)",
        "description": (
            "Original policy: 7 core predicates. Does not require enrichment, "
            "classification, or event capture evidence."
        ),
        "dsl_source": _read_dsl("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0.dsl"),
        "evidence_schema": SWIFT_EVIDENCE_SCHEMA,
    },
    {
        "ref": "B_BALANCE_SHEET_CERTIFICATION",
        "name": "Balance Sheet Adjustment Certification (v1.0)",
        "description": (
            "Multi-entity balance sheet consolidation: 8 predicates covering "
            "subsidiary data, classification, non-financial capture, variance, "
            "lineage, sign-off, intercompany, and FX translation."
        ),
        "dsl_source": _read_dsl("B_BALANCE_SHEET_CERTIFICATION.dsl"),
        "evidence_schema": BS_EVIDENCE_SCHEMA,
    },
    {
        "ref": "B_BALANCE_SHEET_CERTIFICATION_V0_9",
        "name": "Balance Sheet Adjustment Certification (v0.9 — Original)",
        "description": (
            "Original policy: 6 predicates. Does not require non-financial "
            "adjustments capture or data lineage verification."
        ),
        "dsl_source": _read_dsl("B_BALANCE_SHEET_CERTIFICATION_V0_9.dsl"),
        "evidence_schema": BS_EVIDENCE_SCHEMA,
    },
]


# ── Connector configs ─────────────────────────────────────────────────────

def _raw_mappings(schema: dict) -> list[dict]:
    return [
        {"evidence_field": field, "source_path": field}
        for field in schema
    ]


CONNECTOR_CONFIGS = [
    {
        "name": "banking-swift-evidence",
        "provider": "postgresql",
        "description": (
            "SWIFT adjustment integrity evidence from banking source systems. "
            "Caller-supplied payload: the orchestrator pushes evidence directly."
        ),
        "target_boundary_ref": "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4",
        "allowed_acquisition_classes": ["caller_supplied_payload"],
        "evidence_mappings": _raw_mappings(SWIFT_EVIDENCE_SCHEMA),
    },
    {
        "name": "banking-balance-sheet-evidence",
        "provider": "postgresql",
        "description": (
            "Balance sheet consolidation evidence from subsidiary reporting, "
            "classification, reconciliation, and certifier workflow systems. "
            "Caller-supplied payload: the orchestrator pushes evidence directly."
        ),
        "target_boundary_ref": "B_BALANCE_SHEET_CERTIFICATION",
        "allowed_acquisition_classes": ["caller_supplied_payload"],
        "evidence_mappings": _raw_mappings(BS_EVIDENCE_SCHEMA),
    },
]


# ── Flow definitions ──────────────────────────────────────────────────────

def _governed_flow(
    connector_name: str,
    boundary_ref: str,
    assert_message: str,
    defer_title: str,
) -> dict:
    return {
        "schema_version": 1,
        "nodes": [
            {
                "id": "trigger-1",
                "type": "trigger",
                "config": {"connector_name": connector_name},
            },
            {
                "id": "boundary-1",
                "type": "boundary",
                "config": {"boundary_ref": boundary_ref},
            },
            {
                "id": "assert-1",
                "type": "assert_action",
                "config": {"action_type": "log", "message": assert_message},
            },
            {
                "id": "defer-1",
                "type": "defer_action",
                "config": {"action_type": "notification", "title": defer_title},
            },
        ],
        "edges": [
            {"id": "e1", "source": "trigger-1", "target": "boundary-1"},
            {"id": "e2", "source": "boundary-1", "target": "assert-1", "label": "assert"},
            {"id": "e3", "source": "boundary-1", "target": "defer-1", "label": "defer"},
        ],
    }


FLOW_DEFINITIONS = [
    {
        "name": "SWIFT Adjustment Certification Governance",
        "description": (
            "Fires on SWIFT evidence submission. ASSERT logs certification; "
            "DEFER triggers escalation for incomplete, inadmissible, or "
            "prohibited evidence."
        ),
        "definition": _governed_flow(
            connector_name="banking-swift-evidence",
            boundary_ref="B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4",
            assert_message="SWIFT adjustment integrity certified",
            defer_title="SWIFT adjustment certification withheld -- review required",
        ),
    },
    {
        "name": "Balance Sheet Certification Governance",
        "description": (
            "Fires on balance sheet evidence submission. ASSERT logs "
            "certification; DEFER triggers escalation for missing adjustments "
            "or prohibited operations."
        ),
        "definition": _governed_flow(
            connector_name="banking-balance-sheet-evidence",
            boundary_ref="B_BALANCE_SHEET_CERTIFICATION",
            assert_message="Balance sheet adjustment certification complete",
            defer_title="Balance sheet certification withheld -- review required",
        ),
    },
]


# ── Certification models ─────────────────────────────────────────────────

CERTIFICATION_MODELS = [
    {
        "name": "SWIFT Adjustment Integrity Certification",
        "description": (
            "Frozen conformance vector for SWIFT cross-border wire transfer "
            "adjustment integrity across all policy versions (v1.0/v1.2/v1.4)."
        ),
        "evidence_definitions": SWIFT_EVIDENCE_SCHEMA,
    },
    {
        "name": "Balance Sheet Adjustment Certification",
        "description": (
            "Frozen conformance vector for multi-entity balance sheet "
            "consolidation across policy versions (v0.9/v1.0)."
        ),
        "evidence_definitions": BS_EVIDENCE_SCHEMA,
    },
]


# ── Example workloads ─────────────────────────────────────────────────────

EXAMPLE_WORKLOADS = [
    {
        "boundary_ref": "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4",
        "label": "All events active, all sources compliant (ASSERT)",
        "expected_decision": "ASSERT",
        "payload": {
            "originating_swift_valid": 1,
            "beneficiary_account_verified": 1,
            "compliance_screening_passed": 1,
            "human_correction_logged": 1,
            "system_enrichment_logged": 1,
            "adjustment_classification_complete": 1,
            "all_modification_events_captured": 1,
            "dual_authorization_completed": 1,
            "reconciliation_against_source": 1,
            "nostro_balance_confirmed": 1,
        },
    },
    {
        "boundary_ref": "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4",
        "label": "EVT-005 suppressed -- enrichment missing (DEFER)",
        "expected_decision": "DEFER",
        "payload": {
            "originating_swift_valid": 1,
            "beneficiary_account_verified": 1,
            "compliance_screening_passed": 1,
            "human_correction_logged": 1,
            "system_enrichment_logged": 0,
            "adjustment_classification_complete": 0,
            "all_modification_events_captured": 0,
            "dual_authorization_completed": 1,
            "reconciliation_against_source": 1,
            "nostro_balance_confirmed": 1,
        },
    },
    {
        "boundary_ref": "B_BALANCE_SHEET_CERTIFICATION",
        "label": "All adjustments captured (ASSERT)",
        "expected_decision": "ASSERT",
        "payload": {
            "all_subsidiary_data_received": 1,
            "adjustment_events_classified": 1,
            "non_financial_adjustments_captured": 1,
            "reconciliation_variance_within_threshold": 1,
            "data_lineage_verified": 1,
            "certifier_sign_off_obtained": 1,
            "intercompany_eliminations_verified": 1,
            "fx_translation_adjustments_applied": 1,
        },
    },
    {
        "boundary_ref": "B_BALANCE_SHEET_CERTIFICATION",
        "label": "5 missing operational adjustments (DEFER)",
        "expected_decision": "DEFER",
        "payload": {
            "all_subsidiary_data_received": 1,
            "adjustment_events_classified": 1,
            "non_financial_adjustments_captured": 0,
            "reconciliation_variance_within_threshold": 1,
            "data_lineage_verified": 1,
            "certifier_sign_off_obtained": 1,
            "intercompany_eliminations_verified": 1,
            "fx_translation_adjustments_applied": 1,
        },
    },
]


# ── Template metadata ─────────────────────────────────────────────────────

TEMPLATE = {
    "slug": SLUG,
    "name": "Banking Operational Certification",
    "category": "Finance",
    "domain": "finance",
    "description": (
        "Deterministic operational completeness certification for banking "
        "adjustment workflows. Covers SWIFT cross-border wire transfer "
        "adjustment integrity (3 policy versions) and multi-entity balance "
        "sheet consolidation (2 policy versions). Demonstrates three failure "
        "classes (completeness, admissibility, prohibition), governance "
        "cascades, boundary evolution, and adjustment coverage analysis."
    ),
    "outcome_statement": (
        "A certified banking environment where operational completeness is "
        "a governance precondition -- missing evidence, inadmissible sources, "
        "and prohibited operations are caught before certification is granted, "
        "with sealed decisions preserved for deterministic replay."
    ),
    "dsl_source": _read_dsl("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4.dsl"),
    "evidence_schema": SWIFT_EVIDENCE_SCHEMA,
    "boundary_set": BOUNDARY_SET,
    "connector_configs": CONNECTOR_CONFIGS,
    "flow_definitions": FLOW_DEFINITIONS,
    "certification_model": CERTIFICATION_MODELS[0],
    "example_workloads": EXAMPLE_WORKLOADS,
    "integration_code": {},
}


async def main() -> None:
    conn = await asyncpg.connect(DB_DSN)

    existing = await conn.fetchval(
        "SELECT id FROM templates WHERE slug = $1", SLUG
    )

    if existing:
        await conn.execute(
            """UPDATE templates SET
                name = $2,
                category = $3,
                domain = $4,
                description = $5,
                outcome_statement = $6,
                dsl_source = $7,
                evidence_schema = $8,
                boundary_set = $9,
                connector_configs = $10,
                flow_definitions = $11,
                certification_model = $12,
                example_workloads = $13,
                integration_code = $14,
                updated_at = now()
            WHERE slug = $1""",
            TEMPLATE["slug"],
            TEMPLATE["name"],
            TEMPLATE["category"],
            TEMPLATE["domain"],
            TEMPLATE["description"],
            TEMPLATE["outcome_statement"],
            TEMPLATE["dsl_source"],
            json.dumps(TEMPLATE["evidence_schema"]),
            json.dumps(TEMPLATE["boundary_set"]),
            json.dumps(TEMPLATE["connector_configs"]),
            json.dumps(TEMPLATE["flow_definitions"]),
            json.dumps(TEMPLATE["certification_model"]),
            json.dumps(TEMPLATE["example_workloads"]),
            json.dumps(TEMPLATE["integration_code"]),
        )
        print(f"Updated existing template: {SLUG}")
    else:
        await conn.execute(
            """INSERT INTO templates (
                id, slug, name, category, domain, description,
                outcome_statement, dsl_source, evidence_schema,
                boundary_set, connector_configs, flow_definitions,
                certification_model, example_workloads, integration_code,
                status, version, is_official, fork_count, visibility,
                next_version_number, evidence_field_count,
                prohibited_evidence_count, predicate_count,
                onboarding_eligible, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), $1, $2, $3, $4, $5,
                $6, $7, $8,
                $9, $10, $11,
                $12, $13, $14,
                'PUBLISHED', 1, true, 0, 'PUBLIC',
                2, 10, 2, 10, false, now(), now()
            )""",
            TEMPLATE["slug"],
            TEMPLATE["name"],
            TEMPLATE["category"],
            TEMPLATE["domain"],
            TEMPLATE["description"],
            TEMPLATE["outcome_statement"],
            TEMPLATE["dsl_source"],
            json.dumps(TEMPLATE["evidence_schema"]),
            json.dumps(TEMPLATE["boundary_set"]),
            json.dumps(TEMPLATE["connector_configs"]),
            json.dumps(TEMPLATE["flow_definitions"]),
            json.dumps(TEMPLATE["certification_model"]),
            json.dumps(TEMPLATE["example_workloads"]),
            json.dumps(TEMPLATE["integration_code"]),
        )
        print(f"Created template: {SLUG}")

    row = await conn.fetchrow(
        """SELECT name, status,
            jsonb_array_length(boundary_set) as boundaries,
            jsonb_array_length(connector_configs) as connectors,
            jsonb_array_length(flow_definitions) as flows,
            certification_model->>'name' as cert_name
        FROM templates WHERE slug = $1""",
        SLUG,
    )
    print(f"  Name: {row['name']}")
    print(f"  Status: {row['status']}")
    print(f"  Boundaries: {row['boundaries']}")
    print(f"  Connectors: {row['connectors']}")
    print(f"  Flows: {row['flows']}")
    print(f"  Certification: {row['cert_name']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
