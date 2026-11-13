# Copyright 2026 MNC Labs, Inc.
# Author: Asaad Riaz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Idempotent VB-OS Cloud provisioning for the banking reference environment.

Creates and deploys 5 boundaries (3 SWIFT policy versions + 2 Balance Sheet
versions), registers 2 caller-supplied-payload connectors, wires 2 governed
certification flows, and runs 2 certification models. Safe to re-run.

Requires VBOS_API_KEY, VBOS_PROJECT_ID and VBOS_ENVIRONMENT_ID in the
environment (see .env.example).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("VBOS_URL", "https://api.vb-os.org")
API_KEY = os.environ["VBOS_API_KEY"]
PROJECT_ID = os.environ["VBOS_PROJECT_ID"]
ENV_ID = os.environ["VBOS_ENVIRONMENT_ID"]

ROOT = Path(__file__).parent
STATE_FILE = ROOT / ".bootstrap-state.json"

SWIFT_V1_0 = "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0"
SWIFT_V1_2 = "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2"
SWIFT_V1_4 = "B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4"
BS_V1_0 = "B_BALANCE_SHEET_CERTIFICATION"
BS_V0_9 = "B_BALANCE_SHEET_CERTIFICATION_V0_9"

BOUNDARIES = [
    (
        SWIFT_V1_0,
        "SWIFT Adjustment Integrity (Policy v1.0)",
        "Core SWIFT adjustment predicates -- 7 conditions covering origination, "
        "verification, compliance, correction, authorization, reconciliation, "
        "and nostro confirmation.",
    ),
    (
        SWIFT_V1_2,
        "SWIFT Adjustment Integrity (Policy v1.2)",
        "Extends v1.0 with system auto-enrichment requirement -- 8 predicates. "
        "Catches gaps invisible under v1.0.",
    ),
    (
        SWIFT_V1_4,
        "SWIFT Adjustment Integrity (Policy v1.4 -- Current)",
        "Full SWIFT adjustment certification -- 10 predicates including "
        "classification completeness and modification event capture.",
    ),
    (
        BS_V1_0,
        "Balance Sheet Adjustment Certification",
        "Multi-entity balance sheet consolidation -- 8 predicates covering "
        "subsidiary data, classification, non-financial capture, reconciliation, "
        "lineage, sign-off, intercompany, and FX translation.",
    ),
    (
        BS_V0_9,
        "Balance Sheet Adjustment Certification (Policy v0.9)",
        "Original balance sheet policy -- 6 predicates. Does not require "
        "non-financial adjustment capture or data lineage verification.",
    ),
]


def _raw_mappings(fields: list[str]) -> list[dict]:
    return [{"evidence_field": f, "source_path": f} for f in fields]


SWIFT_EVIDENCE_FIELDS = [
    "originating_swift_valid",
    "beneficiary_account_verified",
    "compliance_screening_passed",
    "human_correction_logged",
    "system_enrichment_logged",
    "adjustment_classification_complete",
    "all_modification_events_captured",
    "dual_authorization_completed",
    "reconciliation_against_source",
    "nostro_balance_confirmed",
]

SWIFT_PROHIBITED_FIELDS = [
    "manual_override_without_approval",
    "backdated_adjustment",
]

BS_EVIDENCE_FIELDS = [
    "all_subsidiary_data_received",
    "adjustment_events_classified",
    "non_financial_adjustments_captured",
    "reconciliation_variance_within_threshold",
    "data_lineage_verified",
    "certifier_sign_off_obtained",
    "intercompany_eliminations_verified",
    "fx_translation_adjustments_applied",
]

BS_PROHIBITED_FIELDS = [
    "unreviewed_manual_journal_entry",
    "retroactive_scope_change",
]

CONNECTORS = [
    {
        "name": "banking-swift-evidence",
        "provider": "postgresql",
        "boundary_ref": SWIFT_V1_4,
        "config": {},
        "credentials": {},
        "evidence_mappings": _raw_mappings(
            SWIFT_EVIDENCE_FIELDS + SWIFT_PROHIBITED_FIELDS
        ),
        "allowed_acquisition_classes": ["caller_supplied_payload"],
    },
    {
        "name": "banking-balance-sheet-evidence",
        "provider": "postgresql",
        "boundary_ref": BS_V1_0,
        "config": {},
        "credentials": {},
        "evidence_mappings": _raw_mappings(
            BS_EVIDENCE_FIELDS + BS_PROHIBITED_FIELDS
        ),
        "allowed_acquisition_classes": ["caller_supplied_payload"],
    },
]


SWIFT_CERTIFICATION_VECTOR = {
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
}

BS_CERTIFICATION_VECTOR = {
    "all_subsidiary_data_received": 1,
    "adjustment_events_classified": 1,
    "non_financial_adjustments_captured": 1,
    "reconciliation_variance_within_threshold": 1,
    "data_lineage_verified": 1,
    "certifier_sign_off_obtained": 1,
    "intercompany_eliminations_verified": 1,
    "fx_translation_adjustments_applied": 1,
}

SWIFT_CERTIFICATION_DEFINITIONS = [
    {"field": f, "type": "integer"} for f in SWIFT_EVIDENCE_FIELDS
]

BS_CERTIFICATION_DEFINITIONS = [
    {"field": f, "type": "integer"} for f in BS_EVIDENCE_FIELDS
]


# ── API helpers ──────────────────────────────────────────────────────────


def api(method: str, path: str, body: dict | None = None, attempts: int = 4):
    for attempt in range(attempts):
        req = urllib.request.Request(
            BASE + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < attempts - 1:
                time.sleep(1 + attempt)
                continue
            print(f"  HTTP {e.code} {method} {path}: {e.read().decode()[:300]}")
            return None
    return None


def rows(response: dict | None) -> list:
    if not response:
        return []
    return response.get("data") or response.get("items") or []


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=1) + "\n")


# ── Provisioning ─────────────────────────────────────────────────────────


def provision_boundary(ref: str, name: str, description: str, state: dict) -> None:
    dsl = (ROOT / "boundaries" / f"{ref}.dsl").read_text()

    listing = api("GET", f"/v1/projects/{PROJECT_ID}/boundaries") or {}
    boundary_id = next(
        (b["id"] for b in listing.get("data", []) if b["boundary_ref"] == ref), None
    )

    if not boundary_id:
        created = api("POST", f"/v1/projects/{PROJECT_ID}/boundaries", {
            "boundary_ref": ref,
            "name": name,
            "description": description,
            "dsl_source": dsl,
        })
        if created is None:
            sys.exit(f"boundary creation failed: {ref}")
        boundary_id = created["id"]
        print(f"  {ref}: created")
    else:
        print(f"  {ref}: exists")

    versions = api("GET", f"/v1/projects/{PROJECT_ID}/boundaries/{boundary_id}/versions")
    latest = versions["data"][0]
    detail = api(
        "GET", f"/v1/projects/{PROJECT_ID}/boundaries/{boundary_id}/versions/{latest['id']}"
    ) or {}

    if detail.get("dsl_source", "").strip() != dsl.strip():
        latest = api("POST", f"/v1/projects/{PROJECT_ID}/boundaries/{boundary_id}/versions", {
            "dsl_source": dsl,
            "change_description": "Sync from boundaries/ source of truth",
        })
        print(f"  {ref}: new version {latest['version_number']}")

    version_id, status = latest["id"], latest["status"]

    if status == "DRAFT":
        api("POST", f"/v1/projects/{PROJECT_ID}/boundaries/{boundary_id}/versions/{version_id}/submit", {})
        status = "SUBMITTED"
    if status == "SUBMITTED":
        api("POST", f"/v1/projects/{PROJECT_ID}/boundaries/{boundary_id}/versions/{version_id}/approve", {})
        status = "APPROVED"

    if status in ("APPROVED", "ACTIVE"):
        deployments = api("GET", f"/v1/projects/{PROJECT_ID}/environments/{ENV_ID}/deployments") or {}
        active = any(
            d.get("boundary_version_id") == version_id and d.get("status") == "ACTIVE"
            for d in deployments.get("data", [])
        )
        if active:
            print(f"  {ref}: already deployed")
        else:
            dep = api("POST", f"/v1/projects/{PROJECT_ID}/environments/{ENV_ID}/deployments",
                      {"boundary_version_id": version_id})
            if dep and dep.get("status") == "PENDING_APPROVAL":
                api("POST",
                    f"/v1/projects/{PROJECT_ID}/environments/{ENV_ID}/deployments/{dep['id']}/approve",
                    {"comment": "Banking reference bootstrap"})
            print(f"  {ref}: deployed")

    state.setdefault("boundaries", {})[ref] = {
        "boundary_id": boundary_id,
        "version_id": version_id,
    }


def provision_connectors(state: dict) -> None:
    listing = api("GET", f"/v1/projects/{PROJECT_ID}/connectors") or {}
    by_name = {c["name"]: c for c in listing.get("data", [])}
    connector_ids = state.get("connector_ids", {})

    for spec in CONNECTORS:
        name, config = spec["name"], spec["config"]
        existing = by_name.get(name)

        if existing:
            connector_id = existing["id"]
            patch: dict = {}
            if existing.get("config") != config:
                patch["config"] = config
            creds = spec.get("credentials", {})
            if any(v for v in creds.values()):
                patch["credentials"] = creds
            if patch:
                api("PATCH", f"/v1/projects/{PROJECT_ID}/connectors/{connector_id}", patch)
                print(f"  {name}: updated ({', '.join(patch.keys())})")
            else:
                print(f"  {name}: exists")
        else:
            body = {
                "name": name,
                "provider": spec["provider"],
                "config": config,
                "credentials": spec["credentials"],
                "allowed_acquisition_classes": spec.get(
                    "allowed_acquisition_classes", ["active_provider"]
                ),
                "evidence_mappings": spec["evidence_mappings"],
            }
            created = api("POST", f"/v1/projects/{PROJECT_ID}/connectors", body)
            if created is None:
                sys.exit(f"connector creation failed: {name}")
            connector_id = created["id"]
            print(f"  {name}: created -> {spec['boundary_ref']}")

        api("PUT", f"/v1/projects/{PROJECT_ID}/connectors/{connector_id}/schedule", {
            "auto_evaluate_enabled": True,
            "target_boundary_ref": spec["boundary_ref"],
            "target_environment_id": ENV_ID,
        })
        connector_ids[name] = connector_id

    state["connector_ids"] = connector_ids


def _governed_flow(
    connector_id: str,
    boundary_ref: str,
    boundary_version_id: str,
    assert_message: str,
    defer_title: str,
) -> dict:
    return {
        "schema_version": 1,
        "nodes": [
            {
                "id": "trigger-1",
                "type": "trigger",
                "config": {"connector_id": connector_id},
            },
            {
                "id": "boundary-1",
                "type": "boundary",
                "config": {
                    "boundary_ref": boundary_ref,
                    "boundary_version_id": boundary_version_id,
                },
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


def provision_flows(state: dict) -> None:
    boundaries = state["boundaries"]
    connector_ids = state["connector_ids"]

    flow_specs = [
        (
            "SWIFT Adjustment Certification Governance",
            "Fires on SWIFT evidence submission. ASSERT certifies operational "
            "completeness; DEFER withholds certification with failure class.",
            _governed_flow(
                connector_ids["banking-swift-evidence"],
                SWIFT_V1_4, boundaries[SWIFT_V1_4]["version_id"],
                "SWIFT adjustment certification granted -- all predicates satisfied",
                "SWIFT adjustment certification withheld -- review required",
            ),
        ),
        (
            "Balance Sheet Certification Governance",
            "Fires on balance sheet evidence submission. ASSERT certifies "
            "consolidation completeness; DEFER withholds certification.",
            _governed_flow(
                connector_ids["banking-balance-sheet-evidence"],
                BS_V1_0, boundaries[BS_V1_0]["version_id"],
                "Balance sheet certification granted -- all predicates satisfied",
                "Balance sheet certification withheld -- review required",
            ),
        ),
    ]

    by_name = {f["name"]: f for f in rows(api("GET", f"/v1/projects/{PROJECT_ID}/flows"))}
    flow_ids = state.get("flow_ids", {})

    for name, description, definition in flow_specs:
        existing = by_name.get(name)
        if existing:
            flow_id = existing["id"]
            print(f"  {name}: exists")
        else:
            created = api("POST", f"/v1/projects/{PROJECT_ID}/flows",
                          {"name": name, "description": description})
            if created is None:
                sys.exit(f"flow creation failed: {name}")
            flow_id = created["id"]
            print(f"  {name}: created")

        versions = rows(api("GET", f"/v1/projects/{PROJECT_ID}/flows/{flow_id}/versions"))
        if versions:
            latest = versions[0]
            detail = api("GET",
                         f"/v1/projects/{PROJECT_ID}/flows/{flow_id}/versions/{latest['id']}")
            existing_def = (detail or {}).get("definition", {})
            if json.dumps(existing_def, sort_keys=True) == json.dumps(definition, sort_keys=True):
                flow_ids[name] = flow_id
                print(f"    version up to date")
                continue
            print(f"    definition changed -- creating new version")

        version = api("POST", f"/v1/projects/{PROJECT_ID}/flows/{flow_id}/versions",
                      {"definition": definition})
        if version is None:
            sys.exit(f"flow version failed: {name}")
        vid = version["id"]
        api("POST", f"/v1/projects/{PROJECT_ID}/flows/{flow_id}/versions/{vid}/approve", {})
        api("PATCH", f"/v1/projects/{PROJECT_ID}/flows/{flow_id}", {"status": "ACTIVE"})
        deployed = api("POST", f"/v1/projects/{PROJECT_ID}/flows/{flow_id}/versions/{vid}/deploy",
                       {"environment_id": ENV_ID})
        if deployed is None:
            sys.exit(f"flow deploy failed: {name}")
        print(f"  {name}: deployed")
        flow_ids[name] = flow_id

    state["flow_ids"] = flow_ids


def provision_certifications(state: dict) -> None:
    existing = {m["name"]: m for m in rows(
        api("GET", f"/v1/projects/{PROJECT_ID}/certification-models"))}
    model_ids = state.get("certification_model_ids", {})

    cert_specs = [
        (
            "SWIFT Adjustment Integrity Certification",
            f"Frozen conformance vector for {SWIFT_V1_4}",
            SWIFT_CERTIFICATION_DEFINITIONS,
            SWIFT_CERTIFICATION_VECTOR,
            SWIFT_V1_4,
        ),
        (
            "Balance Sheet Adjustment Certification",
            f"Frozen conformance vector for {BS_V1_0}",
            BS_CERTIFICATION_DEFINITIONS,
            BS_CERTIFICATION_VECTOR,
            BS_V1_0,
        ),
    ]

    for name, description, definitions, vector, boundary_ref in cert_specs:
        model = existing.get(name)
        if model:
            model_id = model["id"]
            print(f"  {name}: exists")
        else:
            created = api("POST", f"/v1/projects/{PROJECT_ID}/certification-models",
                          {"name": name, "description": description})
            if created is None:
                sys.exit(f"certification model creation failed: {name}")
            model_id = created["id"]
            print(f"  {name}: created")
        model_ids[name] = model_id

        if not rows(api("GET",
                        f"/v1/projects/{PROJECT_ID}/certification-models/{model_id}/versions")):
            version = api(
                "POST",
                f"/v1/projects/{PROJECT_ID}/certification-models/{model_id}/versions",
                {
                    "evidence_definitions": definitions,
                    "boundary_version_id": state["boundaries"][boundary_ref]["version_id"],
                    "change_description": "Initial certification model version",
                },
            )
            if version is None:
                sys.exit(f"certification version failed: {name} -- check the "
                         "manage_certifications API key scope")

        run = api("POST", f"/v1/projects/{PROJECT_ID}/certify",
                  {"model": name, "environment": "Development", "evidence": vector})
        if run is None:
            sys.exit(f"certification run failed: {name}")

        status = run.get("status")
        for _ in range(15):
            if status in ("PASSED", "FAILED", "ERROR", "CANCELLED"):
                break
            time.sleep(2)
            poll = api("GET", f"/v1/projects/{PROJECT_ID}/certifications/{run['id']}")
            status = (poll or {}).get("status", status)
        print(f"    run {status}")
        if status != "PASSED":
            sys.exit(f"certification did not pass: {name} ({status})")

    state["certification_model_ids"] = model_ids


# ── Entry point ──────────────────────────────────────────────────────────


def main() -> int:
    state = load_state()
    state["project_id"] = PROJECT_ID
    state["environment_id"] = ENV_ID

    print("Boundaries:")
    for ref, name, description in BOUNDARIES:
        provision_boundary(ref, name, description, state)

    print("Connectors:")
    provision_connectors(state)

    print("Flows:")
    provision_flows(state)

    print("Certifications:")
    provision_certifications(state)

    save_state(state)
    print(f"\nState written to {STATE_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
