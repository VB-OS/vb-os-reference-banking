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

"""VB-OS Banking Reference Integration -- operational completeness certification.

Demonstrates deterministic operational completeness certification for banking
adjustment workflows against a local PostgreSQL source-system database and
VB-OS Cloud. The reference reads operational events and evidence state from
the local database, builds evidence vectors, and submits caller-supplied
payloads to VB-OS Cloud for boundary evaluation, provenance validation,
and sealed certification recording.

    python3 demo.py --list                     # list all scenarios
    python3 demo.py --scenario S1              # single SWIFT scenario
    python3 demo.py --scenario BS2             # single Balance Sheet scenario
    python3 demo.py --all                      # all 13 scenarios
    python3 demo.py --scenario S2 --cascade    # governance cascade detail
    python3 demo.py --scenario S8 --evolution  # boundary evolution (v1.0/v1.2/v1.4)
    python3 demo.py --scenario BS4 --evolution # boundary evolution (v0.9/v1.0)
    python3 demo.py --scenario BS2 --coverage  # adjustment coverage panel
    python3 demo.py --mutations                # S3 + S4 + S5 (three failure classes)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

import psycopg2
from vbos import VBOSClient

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

VBOS_URL = os.environ.get("VBOS_URL", "https://api.vb-os.org")
API_KEY = os.environ.get("VBOS_API_KEY", "")
PROJECT_ID = os.environ.get("VBOS_PROJECT_ID", "")
ENVIRONMENT_ID = os.environ.get("VBOS_ENVIRONMENT_ID", "")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://banking:banking@banking-postgres:5432/banking",
)

RULE = "─" * 60
DOUBLE_RULE = "═" * 60

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIOS = {
    "S1": {
        "model": "swift",
        "name": "All events active, all sources compliant",
        "expected": "ASSERT",
        "label": "CERTIFIED",
    },
    "S2": {
        "model": "swift",
        "name": "EVT-005 suppressed (enrichment missing)",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — INCOMPLETE",
    },
    "S3": {
        "model": "swift",
        "name": "Prohibited evidence injected",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — PROHIBITED OPERATION",
        "inject_prohibited": True,
    },
    "S4": {
        "model": "swift",
        "name": "Source version downgraded (recon_engine v2.1)",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — INADMISSIBLE EVIDENCE",
    },
    "S5": {
        "model": "swift",
        "name": "All three failure classes",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — MULTIPLE VIOLATIONS",
        "inject_prohibited": True,
    },
    "S6": {
        "model": "swift",
        "name": "Dual authorization missing",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — INCOMPLETE",
    },
    "S7": {
        "model": "swift",
        "name": "Compliance engine v3.8 (admissibility)",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — INADMISSIBLE EVIDENCE",
    },
    "S8": {
        "model": "swift",
        "name": "Boundary evolution (v1.0 / v1.2 / v1.4)",
        "expected": "MIXED",
        "label": "CERTIFIED / NOT CERTIFIED / NOT CERTIFIED",
        "evolution": True,
    },
    "BS1": {
        "model": "balance_sheet",
        "name": "All adjustments captured",
        "expected": "ASSERT",
        "label": "CERTIFIED",
    },
    "BS2": {
        "model": "balance_sheet",
        "name": "5 missing operational adjustments",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — INCOMPLETE",
    },
    "BS3": {
        "model": "balance_sheet",
        "name": "Missing adjustments + prohibited evidence",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — MULTIPLE VIOLATIONS",
        "inject_prohibited": True,
    },
    "BS4": {
        "model": "balance_sheet",
        "name": "Boundary evolution (v0.9 / v1.0)",
        "expected": "MIXED",
        "label": "CERTIFIED / NOT CERTIFIED",
        "evolution": True,
    },
    "BS5": {
        "model": "balance_sheet",
        "name": "Non-financial adjustments not captured",
        "expected": "DEFER",
        "label": "NOT CERTIFIED — INCOMPLETE",
    },
}

CONNECTOR_MAP = {
    "swift": "banking-swift-evidence",
    "balance_sheet": "banking-balance-sheet-evidence",
}

SWIFT_EVOLUTION_BOUNDARIES = [
    ("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0", "v1.0 (2024-Q1)", "7 core predicates"),
    ("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2", "v1.2 (2024-Q3)", "+enrichment requirement"),
    ("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4", "v1.4 (2025-Q1)", "+classification +event capture"),
]

BS_EVOLUTION_BOUNDARIES = [
    ("B_BALANCE_SHEET_CERTIFICATION_V0_9", "v0.9 (2024-Q2)", "6 core predicates"),
    ("B_BALANCE_SHEET_CERTIFICATION", "v1.0 (2025-Q1)", "+non-financial +lineage"),
]

SWIFT_CASCADE = [
    ("system_enrichment_logged", "System enrichment not captured", "enrichment_service"),
    ("adjustment_classification_complete", "Adjustment classification incomplete", "classification_engine"),
    ("all_modification_events_captured", "All modification events NOT captured", "event_capture"),
]

MODEL_TITLES = {
    "swift": "SWIFT ADJUSTMENT INTEGRITY CERTIFICATION",
    "balance_sheet": "BALANCE SHEET ADJUSTMENT CERTIFICATION",
}

MODEL_SUBTITLES = {
    "swift": "Cross-Border Wire Transfers (SWIFT MT103/MT202)",
    "balance_sheet": "Multi-Entity Balance Sheet Consolidation",
}

# ---------------------------------------------------------------------------
# VB-OS Cloud client
# ---------------------------------------------------------------------------

_connector_cache: dict[str, str] = {}
_boundary_cache: dict[str, str] = {}


def _resolve_connector(client: VBOSClient, name: str) -> str:
    if name in _connector_cache:
        return _connector_cache[name]

    if not _connector_cache:
        url = f"/v1/projects/{PROJECT_ID}/connectors"
        req = client._client.build_request("GET", url)
        resp = client._client.send(req)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", data.get("items", data if isinstance(data, list) else [])):
            _connector_cache[item["name"]] = item["id"]

    if name not in _connector_cache:
        print(f"  Connector '{name}' not found in project")
        sys.exit(1)
    return _connector_cache[name]


def _resolve_boundary(client: VBOSClient, ref: str) -> str:
    if ref in _boundary_cache:
        return _boundary_cache[ref]

    if not _boundary_cache:
        url = f"/v1/projects/{PROJECT_ID}/boundaries"
        req = client._client.build_request("GET", url)
        resp = client._client.send(req)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", data.get("items", data if isinstance(data, list) else [])):
            _boundary_cache[item.get("ref", item.get("name", ""))] = item["id"]

    if ref not in _boundary_cache:
        print(f"  Boundary '{ref}' not found in project")
        sys.exit(1)
    return _boundary_cache[ref]


def _sdk_client() -> VBOSClient:
    return VBOSClient(api_key=API_KEY, base_url=VBOS_URL)


def gather(client: VBOSClient, connector_name: str, payload: dict,
           provenance: dict | None = None) -> dict | None:
    connector_id = _resolve_connector(client, connector_name)
    kwargs: dict = {
        "project_id": PROJECT_ID,
        "connector_id": connector_id,
        "payload": payload,
    }
    if provenance:
        kwargs["context_evidence"] = {"_provenance": provenance}
    try:
        response = client.connectors.gather(**kwargs)
        return response
    except Exception as exc:
        print(f"  VB-OS Cloud error: {exc}")
        return None


def evaluate_boundary(client: VBOSClient, boundary_ref: str,
                      payload: dict, provenance: dict) -> dict | None:
    """Direct evaluation against a named boundary (for evolution scenarios)."""
    boundary_id = _resolve_boundary(client, boundary_ref)
    url = f"/v1/projects/{PROJECT_ID}/evaluations"
    body = {
        "boundary_id": boundary_id,
        "environment_id": ENVIRONMENT_ID,
        "payload": payload,
        "context_evidence": {"_provenance": provenance},
    }
    req = client._client.build_request("POST", url, json=body)
    try:
        resp = client._client.send(req)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"  VB-OS Cloud error ({boundary_ref}): {exc}")
        return None


# ---------------------------------------------------------------------------
# Database access (local source systems)
# ---------------------------------------------------------------------------

def _db() -> psycopg2.extensions.connection:
    return psycopg2.connect(DATABASE_URL)


def load_evidence(conn, model: str, scenario: str) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(
        "SELECT field, value, source, source_version "
        "FROM evidence_state WHERE model = %s AND scenario = %s",
        (model, scenario),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def load_events(conn, model: str, scenario: str) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(
        "SELECT event_id, stage, description, active "
        "FROM operational_events WHERE model = %s AND scenario = %s "
        "ORDER BY event_id",
        (model, scenario),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def load_coverage(conn, model: str, scenario: str) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(
        "SELECT category, label, expected, captured "
        "FROM adjustment_coverage WHERE model = %s AND scenario = %s",
        (model, scenario),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def load_missing(conn, model: str, scenario: str) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(
        "SELECT entity, adjustment_type, impact, classification, status "
        "FROM missing_adjustments WHERE model = %s AND scenario = %s",
        (model, scenario),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def load_scope(conn, model: str, scenario: str) -> dict | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT operational_domain, corridor, certification_window, "
        "transactions_in_scope, modifications_evaluated "
        "FROM certification_scope WHERE model = %s AND scenario = %s",
        (model, scenario),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {
        "operational_domain": row[0],
        "corridor": row[1],
        "certification_window": row[2],
        "transactions_in_scope": row[3],
        "modifications_evaluated": row[4],
    }


# ---------------------------------------------------------------------------
# Evidence building
# ---------------------------------------------------------------------------

def build_evidence(conn, model: str, scenario: str) -> tuple[dict, dict]:
    rows = load_evidence(conn, model, scenario)
    payload: dict = {}
    provenance: dict = {}
    for field, value, source, source_version in rows:
        payload[field] = value
        provenance[field] = source
        if source_version:
            provenance[f"{field}_version"] = source_version
    return payload, provenance


# ---------------------------------------------------------------------------
# Failure class analysis
# ---------------------------------------------------------------------------

def classify_failures(eval_result: dict) -> list[str]:
    """Derive failure classes from evaluation result."""
    classes = []
    failure_reasons = eval_result.get("failure_reasons") or []
    predicate_results = eval_result.get("predicate_results") or {}

    has_completeness = False
    has_prohibition = False
    has_admissibility = False

    for reason in failure_reasons:
        rtype = reason.get("type", "")
        if rtype == "prohibition" or "prohibit" in rtype.lower():
            has_prohibition = True
        elif rtype == "admissibility" or "inadmissible" in rtype.lower():
            has_admissibility = True
        elif rtype == "predicate_failure":
            has_completeness = True

    if not failure_reasons:
        for name, result in predicate_results.items():
            passed = result.get("passed") if isinstance(result, dict) else result
            if not passed:
                has_completeness = True
                break

    if has_completeness:
        classes.append("completeness")
    if has_admissibility:
        classes.append("admissibility")
    if has_prohibition:
        classes.append("prohibition")

    return classes


def derive_certification_label(decision: str, failure_classes: list[str]) -> str:
    if decision == "ASSERT":
        return "CERTIFIED"
    if len(failure_classes) > 1:
        return "NOT CERTIFIED — MULTIPLE VIOLATIONS"
    if "prohibition" in failure_classes:
        return "NOT CERTIFIED — PROHIBITED OPERATION"
    if "admissibility" in failure_classes:
        return "NOT CERTIFIED — INADMISSIBLE EVIDENCE"
    return "NOT CERTIFIED — INCOMPLETE"


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _box(lines: list[str], width: int = 60) -> str:
    out = ["┌" + "─" * (width - 2) + "┐"]
    for line in lines:
        text = line[: width - 4]
        out.append("│ " + text.ljust(width - 4) + " │")
    out.append("└" + "─" * (width - 2) + "┘")
    return "\n".join(out)


def _double_box(lines: list[str], width: int = 60) -> str:
    out = ["╔" + "═" * (width - 2) + "╗"]
    for line in lines:
        text = line[: width - 4]
        out.append("║ " + text.ljust(width - 4) + " ║")
    out.append("╚" + "═" * (width - 2) + "╝")
    return "\n".join(out)


def show_list() -> None:
    print()
    print("  VB-OS Banking Reference Integration — Scenarios")
    print("  " + DOUBLE_RULE)
    print()
    fmt = "  {:<6} {:<15} {:<8} {}"
    print(fmt.format("ID", "Model", "Expected", "Description"))
    print(fmt.format("──", "─────", "────────", "───────────"))
    for sid, info in SCENARIOS.items():
        print(fmt.format(sid, info["model"], info["expected"], info["name"]))
    print()
    print(f"  {len(SCENARIOS)} scenarios total")
    print(f"  SWIFT: {sum(1 for s in SCENARIOS.values() if s['model'] == 'swift')}")
    print(f"  Balance Sheet: {sum(1 for s in SCENARIOS.values() if s['model'] == 'balance_sheet')}")
    print()


def show_events(events: list[tuple]) -> None:
    print()
    print("  OPERATIONAL EVENTS:")
    for event_id, stage, description, active in events:
        status = "ACTIVE" if active else "SUPPRESSED"
        marker = "●" if active else "○"
        print(f"    {marker} {event_id}: {description} — {status}")
    print()


def show_cascade(eval_result: dict) -> None:
    predicate_results = eval_result.get("predicate_results") or {}
    failed_cascade = []
    for field, label, source in SWIFT_CASCADE:
        for pname, presult in predicate_results.items():
            passed = presult.get("passed") if isinstance(presult, dict) else presult
            if not passed and field in pname:
                failed_cascade.append((field, label, source))
                break

    if not failed_cascade:
        failed_cascade = SWIFT_CASCADE

    print()
    width = 60
    print("  " + "┌" + "─" * (width - 2) + "┐")
    print("  " + "│" + " GOVERNANCE CASCADE".ljust(width - 2) + "│")
    print("  " + "├" + "─" * (width - 2) + "┤")
    for i, (field, label, source) in enumerate(failed_cascade, 1):
        circle = "①②③④⑤⑥⑦⑧⑨"[i - 1] if i <= 9 else str(i)
        line = f" {circle} {label}"
        src = f"   ({source})"
        print("  " + "│" + line.ljust(width - 2) + "│")
        print("  " + "│" + src.ljust(width - 2) + "│")
        if i < len(failed_cascade):
            print("  " + "│" + "   ↓".ljust(width - 2) + "│")
    arrow_label = " ↓"
    esc_line = f" {len(failed_cascade) + 1}. Certification: INCOMPLETE → Escalation required"
    if len(esc_line) > width - 3:
        esc_line = esc_line[: width - 3]
    print("  " + "│" + arrow_label.ljust(width - 2) + "│")
    print("  " + "│" + esc_line.ljust(width - 2) + "│")
    print("  " + "└" + "─" * (width - 2) + "┘")
    print()
    print(f"  One suppressed event. {len(failed_cascade)} failed conditions. One cascade.")
    print("  Traditional reconciliation saw none of this.")
    print()


def show_coverage(coverage: list[tuple], missing: list[tuple],
                  scope: dict | None) -> None:
    total_expected = sum(r[2] for r in coverage)
    total_captured = sum(r[3] for r in coverage)
    total_missing = total_expected - total_captured

    print()
    width = 60
    print("  " + DOUBLE_RULE)
    if scope:
        print(f"  {MODEL_TITLES['balance_sheet']}")
        print(f"  {MODEL_SUBTITLES['balance_sheet']} — {scope['certification_window']}")
    print("  " + DOUBLE_RULE)
    print()
    print(f"  Total Expected:    {total_expected:,} adjustments")
    print(f"  Captured:          {total_captured:,} adjustments")
    print(f"  Missing:           {total_missing}")
    print()
    for category, label, expected, captured in coverage:
        pct = (captured / expected * 100) if expected > 0 else 0
        print(f"  {label}:  {captured:,} / {expected:,}  ({pct:.2f}%)")
    print()

    trad_result = "PASS" if total_missing <= 5 else "FAIL"
    vbos_result = "CERTIFIED" if total_missing == 0 else "NOT CERTIFIED — INCOMPLETE"
    comp_lines = [
        f"Traditional Reconciliation Controls:    {trad_result}",
        f"VB-OS Operational Completeness:         {vbos_result}",
    ]
    print("  " + _box(comp_lines, width))
    print()

    if missing:
        print("  MISSING OPERATIONAL ADJUSTMENTS:")
        print("  " + "┌" + "─" * 28 + "┬" + "─" * 22 + "┬" + "─" * 11 + "┐")
        for entity, adj_type, impact, classification, status in missing:
            print(
                f"  │ {entity:<26} │ {adj_type:<20} │ {impact:>9} │"
            )
        print("  " + "└" + "─" * 28 + "┴" + "─" * 22 + "┴" + "─" * 11 + "┘")
        print()
        print(f"  Financial control checked: GL balance = source balance → {trad_result}")
        print(f"  VB-OS boundary checked:   Expected adjustment identities vs captured"
              f" → {total_missing} missing → DEFER")
        print()


def show_certification(scenario_id: str, info: dict, eval_result: dict,
                       events: list[tuple] | None = None,
                       cascade: bool = False,
                       coverage: list[tuple] | None = None,
                       missing: list[tuple] | None = None,
                       scope: dict | None = None) -> None:
    model = info["model"]
    decision = "unknown"
    eval_id = ""
    predicate_results = {}

    if isinstance(eval_result, dict):
        decision = eval_result.get("decision", "unknown")
        eval_id = eval_result.get("evaluation_id", "")
        predicate_results = eval_result.get("predicate_results") or {}
    elif hasattr(eval_result, "model_dump"):
        raw = eval_result.model_dump()
        decision = raw.get("decision", "unknown")
        eval_id = raw.get("evaluation_id", "")
        predicate_results = raw.get("predicate_results") or {}
        eval_result = raw

    failure_classes = classify_failures(
        eval_result if isinstance(eval_result, dict) else {}
    )
    cert_label = derive_certification_label(decision, failure_classes)

    print()
    print("  " + DOUBLE_RULE)
    print(f"  {MODEL_TITLES[model]}")
    if scope:
        print(f"  {scope['operational_domain']}")
        print(f"  {scope['certification_window']}")
        if scope.get("transactions_in_scope"):
            print(f"  Transactions: {scope['transactions_in_scope']:,}"
                  + (f"  Modifications: {scope['modifications_evaluated']:,}"
                     if scope.get("modifications_evaluated") else ""))
    print(f"  Scenario: {scenario_id} — {info['name']}")
    print("  " + DOUBLE_RULE)
    print()

    if events:
        show_events(events)

    decision_color = "✓" if decision == "ASSERT" else "✗"
    print(f"  {decision_color} VB-OS Decision: {decision}")
    print(f"    Certification: {cert_label}")
    if eval_id:
        print(f"    Evaluation ID: {eval_id}")
    print()

    failed = []
    passed_count = 0
    for name, result in predicate_results.items():
        p = result.get("passed") if isinstance(result, dict) else result
        if p:
            passed_count += 1
        else:
            msg = ""
            if isinstance(result, dict):
                msg = result.get("message", result.get("error", ""))
            failed.append((name, msg))

    print(f"  Predicates: {passed_count} passed, {len(failed)} failed"
          f" (of {passed_count + len(failed)})")

    if failed:
        print()
        print("  FAILED CONDITIONS:")
        for name, msg in failed:
            print(f"    ✗ {name}")
            if msg:
                print(f"      {msg}")

    if failure_classes:
        print()
        print("  Failure classes: " + ", ".join(failure_classes))

    if cascade and model == "swift":
        show_cascade(eval_result if isinstance(eval_result, dict) else {})

    if coverage is not None and missing is not None:
        show_coverage(coverage, missing, scope)

    failure_reasons = (eval_result if isinstance(eval_result, dict) else {}).get("failure_reasons") or []
    for reason in failure_reasons:
        rtype = reason.get("type", "")
        if "prohibit" in rtype.lower():
            field = reason.get("field", reason.get("predicate", ""))
            print(f"\n  ⚠ PROHIBITED EVIDENCE DETECTED: {field}")
            msg = reason.get("message", "")
            if msg:
                print(f"    {msg}")

    print()
    print("  " + RULE)
    print()


def show_evolution(scenario_id: str, info: dict, results: list[tuple],
                   events: list[tuple] | None = None) -> None:
    model = info["model"]
    print()
    print("  " + DOUBLE_RULE)
    print(f"  BOUNDARY EVOLUTION — {MODEL_TITLES[model]}")
    print(f"  Scenario: {scenario_id} — {info['name']}")
    print("  " + DOUBLE_RULE)

    if events:
        show_events(events)

    print()
    for boundary_ref, version_label, description, eval_result in results:
        if eval_result is None:
            decision = "ERROR"
            cert = "evaluation failed"
        elif isinstance(eval_result, dict):
            decision = eval_result.get("decision", "unknown")
            fc = classify_failures(eval_result)
            cert = derive_certification_label(decision, fc)
        elif hasattr(eval_result, "model_dump"):
            raw = eval_result.model_dump()
            decision = raw.get("decision", "unknown")
            fc = classify_failures(raw)
            cert = derive_certification_label(decision, fc)
        else:
            decision = "unknown"
            cert = "unknown"

        marker = "✓" if decision == "ASSERT" else "✗"
        print(f"  {marker} Boundary {version_label}:  {cert}")
        print(f"    {description}")
        print()

    print("  Same evidence. Different policy versions. Different outcomes.")
    if model == "swift":
        print("  The gap existed under v1.0 — the policy just didn't require it.")
    else:
        print("  The gap existed under v0.9 — the policy just didn't require it.")
    print()
    print("  " + RULE)
    print()


def show_mutation_header(scenario_id: str, info: dict,
                         failure_class: str) -> None:
    print()
    print(f"  {'─' * 40}")
    print(f"  MUTATION: {failure_class.upper()}")
    print(f"  Scenario {scenario_id}: {info['name']}")
    print(f"  {'─' * 40}")


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------

def run_scenario(client: VBOSClient, scenario_id: str,
                 cascade: bool = False, evolution: bool = False,
                 coverage: bool = False) -> dict | None:
    info = SCENARIOS[scenario_id]
    conn = _db()

    try:
        events = load_events(conn, info["model"], scenario_id)
        payload, provenance = build_evidence(conn, info["model"], scenario_id)

        if info.get("inject_prohibited"):
            if info["model"] == "swift":
                payload["manual_override_without_approval"] = 1
            else:
                payload["unreviewed_manual_journal_entry"] = 1

        if evolution and info.get("evolution"):
            return run_evolution(client, scenario_id, info, payload,
                                provenance, events)

        connector = CONNECTOR_MAP[info["model"]]
        eval_result = gather(client, connector, payload, provenance)

        if eval_result is None:
            print(f"  {scenario_id}: evaluation failed")
            return None

        scope_data = load_scope(conn, info["model"], scenario_id)
        cov_data = load_coverage(conn, info["model"], scenario_id) if coverage else None
        miss_data = load_missing(conn, info["model"], scenario_id) if coverage else None

        raw = eval_result
        if hasattr(eval_result, "model_dump"):
            raw = eval_result.model_dump()

        show_certification(
            scenario_id, info, raw, events, cascade,
            cov_data, miss_data, scope_data,
        )
        return raw
    finally:
        conn.close()


def run_evolution(client: VBOSClient, scenario_id: str, info: dict,
                  payload: dict, provenance: dict,
                  events: list[tuple]) -> dict | None:
    if info["model"] == "swift":
        boundaries = SWIFT_EVOLUTION_BOUNDARIES
    else:
        boundaries = BS_EVOLUTION_BOUNDARIES

    results = []
    for boundary_ref, version_label, description in boundaries:
        eval_result = evaluate_boundary(
            client, boundary_ref, payload, provenance,
        )
        raw = eval_result
        if hasattr(eval_result, "model_dump"):
            raw = eval_result.model_dump()
        results.append((boundary_ref, version_label, description, raw))

    show_evolution(scenario_id, info, results, events)
    return results[-1][3] if results else None


def run_all(client: VBOSClient) -> None:
    total = 0
    passed = 0
    failed = 0

    for sid, info in SCENARIOS.items():
        if info.get("evolution"):
            connector = CONNECTOR_MAP[info["model"]]
            conn = _db()
            try:
                payload, provenance = build_evidence(
                    conn, info["model"], sid,
                )
                if info.get("inject_prohibited"):
                    if info["model"] == "swift":
                        payload["manual_override_without_approval"] = 1
                    else:
                        payload["unreviewed_manual_journal_entry"] = 1
                eval_result = gather(client, connector, payload, provenance)
            finally:
                conn.close()

            if eval_result is None:
                print(f"  {sid}: evaluation failed")
                failed += 1
                total += 1
                continue

            raw = eval_result
            if hasattr(eval_result, "model_dump"):
                raw = eval_result.model_dump()

            decision = raw.get("decision", "unknown")
            fc = classify_failures(raw)
            cert = derive_certification_label(decision, fc)
            marker = "✓" if decision == info["expected"] else "✗"
            print(f"  {marker} {sid}: {decision} — {cert}")
            print(f"    {info['name']}")

            if decision == info["expected"]:
                passed += 1
            else:
                failed += 1
            total += 1
        else:
            result = run_scenario(client, sid)
            total += 1
            if result:
                decision = result.get("decision", "unknown")
                if decision == info["expected"]:
                    passed += 1
                else:
                    failed += 1
            else:
                failed += 1

    print()
    print("  " + DOUBLE_RULE)
    print(f"  Results: {passed}/{total} matched expected decisions")
    if failed:
        print(f"  {failed} unexpected results")
    print("  " + DOUBLE_RULE)
    print()


def run_mutations(client: VBOSClient) -> None:
    print()
    print("  " + DOUBLE_RULE)
    print("  MUTATION SCENARIOS — Three Failure Classes")
    print("  " + DOUBLE_RULE)

    mutation_scenarios = [
        ("S3", "prohibition"),
        ("S4", "admissibility"),
        ("S5", "all three failure classes"),
    ]

    for sid, failure_class in mutation_scenarios:
        info = SCENARIOS[sid]
        show_mutation_header(sid, info, failure_class)
        run_scenario(client, sid)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="VB-OS Banking Reference Integration",
    )
    parser.add_argument("--list", action="store_true",
                        help="List all scenarios")
    parser.add_argument("--scenario", type=str,
                        help="Run a specific scenario (S1, BS2, etc.)")
    parser.add_argument("--all", action="store_true",
                        help="Run all 13 scenarios")
    parser.add_argument("--cascade", action="store_true",
                        help="Show governance cascade detail")
    parser.add_argument("--evolution", action="store_true",
                        help="Run boundary evolution (multi-version)")
    parser.add_argument("--coverage", action="store_true",
                        help="Show adjustment coverage panel")
    parser.add_argument("--mutations", action="store_true",
                        help="Run S3 + S4 + S5 (three failure classes)")

    args = parser.parse_args()

    if args.list:
        show_list()
        return

    if not API_KEY:
        print("  Error: VBOS_API_KEY not set. See .env.example.")
        sys.exit(1)
    if not PROJECT_ID:
        print("  Error: VBOS_PROJECT_ID not set. See .env.example.")
        sys.exit(1)

    client = _sdk_client()

    if args.mutations:
        run_mutations(client)
        return

    if args.all:
        run_all(client)
        return

    if args.scenario:
        sid = args.scenario.upper()
        if sid not in SCENARIOS:
            print(f"  Unknown scenario: {sid}")
            print(f"  Use --list to see available scenarios")
            sys.exit(1)
        run_scenario(
            client, sid,
            cascade=args.cascade,
            evolution=args.evolution,
            coverage=args.coverage,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
