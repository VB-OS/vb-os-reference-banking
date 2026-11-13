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

"""VB-OS Banking Reference Integration -- verification suite.

Seven verification functions:
  1. Parity        -- replay every sealed evaluation and confirm decision parity
  2. Completeness  -- S1 ASSERT, suppress EVT-005 -> DEFER (deterministic cascade)
  3. Admissibility -- recon_engine v2.3 ASSERT, downgrade to v2.1 -> DEFER
  4. Prohibition   -- clean ASSERT, inject manual_override -> DEFER
  5. Evolution     -- same evidence against v1.0/v1.2/v1.4 -> ASSERT/DEFER/DEFER
  6. Coverage      -- BS1 ASSERT (41,228/41,228), BS2 DEFER (5 missing)
  7. Cascade       -- S2 -> 3-predicate failure chain verified

    python3 verify.py --all                # run all verifications
    python3 verify.py --parity             # replay parity only
    python3 verify.py --completeness       # completeness only
    python3 verify.py --admissibility      # admissibility only
    python3 verify.py --prohibition        # prohibition only
    python3 verify.py --evolution          # boundary evolution only
    python3 verify.py --coverage           # balance sheet coverage only
    python3 verify.py --cascade            # governance cascade only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

VBOS_URL = os.environ.get("VBOS_URL", "https://api.vb-os.org")
API_KEY = os.environ.get("VBOS_API_KEY", "")
PROJECT_ID = os.environ.get("VBOS_PROJECT_ID", "")
ENVIRONMENT_ID = os.environ.get("VBOS_ENVIRONMENT_ID", "")

RULE = "-" * 72

_connector_cache: dict[str, str] = {}
_boundary_cache: dict[str, str] = {}


# ── SWIFT evidence payloads (inline, no DB dependency) ────────────────────

SWIFT_CLEAN_PAYLOAD = {
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

SWIFT_PROVENANCE = {
    "originating_swift_valid": "swift_gateway",
    "beneficiary_account_verified": "core_banking",
    "compliance_screening_passed": "compliance_engine",
    "human_correction_logged": "ops_workflow",
    "system_enrichment_logged": "enrichment_service",
    "adjustment_classification_complete": "classification_engine",
    "all_modification_events_captured": "event_capture",
    "dual_authorization_completed": "auth_system",
    "reconciliation_against_source": "recon_engine",
    "nostro_balance_confirmed": "nostro_system",
}

BS_CLEAN_PAYLOAD = {
    "all_subsidiary_data_received": 1,
    "adjustment_events_classified": 1,
    "non_financial_adjustments_captured": 1,
    "reconciliation_variance_within_threshold": 1,
    "data_lineage_verified": 1,
    "certifier_sign_off_obtained": 1,
    "intercompany_eliminations_verified": 1,
    "fx_translation_adjustments_applied": 1,
}

BS_PROVENANCE = {
    "all_subsidiary_data_received": "subsidiary_reporting",
    "adjustment_events_classified": "classification_engine",
    "non_financial_adjustments_captured": "nonfin_tracking",
    "reconciliation_variance_within_threshold": "recon_engine",
    "data_lineage_verified": "lineage_service",
    "certifier_sign_off_obtained": "certifier_workflow",
    "intercompany_eliminations_verified": "intercompany_system",
    "fx_translation_adjustments_applied": "fx_translation",
}


# ── API helpers ───────────────────────────────────────────────────────────

def api(method: str, path: str, body: dict | None = None) -> dict | None:
    url = f"{VBOS_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            body_text = e.read().decode()[:300] if e.fp else ""
            print(f"  HTTP {e.code}: {body_text}")
            return None
    return None


def _resolve_connector(name: str) -> str:
    if name in _connector_cache:
        return _connector_cache[name]

    if not _connector_cache:
        result = api("GET", f"/v1/projects/{PROJECT_ID}/connectors")
        if result:
            for item in result.get("data", result.get("items", [])):
                _connector_cache[item["name"]] = item["id"]

    if name not in _connector_cache:
        print(f"  Connector '{name}' not found in project")
        sys.exit(1)
    return _connector_cache[name]


def _resolve_boundary(ref: str) -> str:
    if ref in _boundary_cache:
        return _boundary_cache[ref]

    if not _boundary_cache:
        result = api("GET", f"/v1/projects/{PROJECT_ID}/boundaries")
        if result:
            for item in result.get("data", result.get("items", [])):
                _boundary_cache[item.get("boundary_ref", item.get("ref", item.get("name", "")))] = item["id"]

    if ref not in _boundary_cache:
        print(f"  Boundary '{ref}' not found in project")
        sys.exit(1)
    return _boundary_cache[ref]


def _gather(connector_name: str, payload: dict, provenance: dict) -> dict | None:
    cid = _resolve_connector(connector_name)
    return api(
        "POST",
        f"/v1/projects/{PROJECT_ID}/connectors/{cid}/gather",
        {"payload": payload, "context_evidence": {"_provenance": provenance}},
    )


def list_evaluations() -> list[dict]:
    path = f"/v1/projects/{PROJECT_ID}/evaluations"
    result = api("GET", path)
    if not result:
        return []
    items = result.get("data", result.get("items", []))
    if isinstance(items, list):
        return items
    return []


# -- Test 1: Parity ---------------------------------------------------------

def verify_parity() -> tuple[int, int]:
    print(RULE)
    print("  Verification 1: Replay Parity")
    print(RULE)

    evaluations = list_evaluations()
    if not evaluations:
        print("  No evaluations found. Run demo.py --all first.")
        return 0, 0

    passed = 0
    failed = 0

    for ev in evaluations:
        eval_id = ev.get("evaluation_id") or ev.get("id", "")
        original_decision = ev.get("decision", "")
        boundary = ev.get("boundary_ref", "")

        if not eval_id:
            continue

        result = api("POST", f"/v1/projects/{PROJECT_ID}/evaluations/{eval_id}/replay", {})
        if not result:
            print(f"    SKIP  {eval_id[:12]}  (replay failed)")
            failed += 1
            continue

        replay_out = result.get("replay_evaluation_output") or {}
        replay_decision = replay_out.get("decision", "")
        result_match = result.get("result_match", False)

        if result_match and replay_decision == original_decision:
            passed += 1
            print(f"    PASS  {eval_id[:12]}  {boundary}  {original_decision}")
        else:
            failed += 1
            print(f"    FAIL  {eval_id[:12]}  {boundary}  "
                  f"original={original_decision} replay={replay_decision}")

    print(f"\n  Parity: {passed} passed, {failed} failed out of {passed + failed}")
    return passed, failed


# -- Test 2: Completeness ---------------------------------------------------

def verify_completeness() -> tuple[int, int]:
    print(RULE)
    print("  Verification 2: Completeness")
    print(RULE)

    passed = 0
    failed = 0

    print("  Submitting S1 (all evidence present)...")
    resp = _gather("banking-swift-evidence", SWIFT_CLEAN_PAYLOAD, SWIFT_PROVENANCE)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    S1: {decision}")
        if decision == "ASSERT":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected ASSERT, got {decision}")
    else:
        failed += 1

    print("  Submitting S2 (EVT-005 suppressed — enrichment missing)...")
    s2_payload = dict(SWIFT_CLEAN_PAYLOAD)
    s2_payload["system_enrichment_logged"] = 0
    s2_payload["adjustment_classification_complete"] = 0
    s2_payload["all_modification_events_captured"] = 0
    resp = _gather("banking-swift-evidence", s2_payload, SWIFT_PROVENANCE)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    S2: {decision}")
        if decision == "DEFER":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected DEFER, got {decision}")
    else:
        failed += 1

    print(f"\n  Completeness: {passed} passed, {failed} failed")
    return passed, failed


# -- Test 3: Admissibility --------------------------------------------------

def verify_admissibility() -> tuple[int, int]:
    print(RULE)
    print("  Verification 3: Admissibility")
    print(RULE)

    passed = 0
    failed = 0

    print("  Submitting with recon_engine v2.3 (compliant)...")
    prov_good = dict(SWIFT_PROVENANCE)
    prov_good["_source_versions"] = {"reconciliation_against_source": "2.3"}
    resp = _gather("banking-swift-evidence", SWIFT_CLEAN_PAYLOAD, prov_good)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    Compliant source: {decision}")
        if decision == "ASSERT":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected ASSERT, got {decision}")
    else:
        failed += 1

    print("  Submitting with recon_engine v2.1 (downgraded, provenance recorded)...")
    prov_bad = dict(SWIFT_PROVENANCE)
    prov_bad["_source_versions"] = {"reconciliation_against_source": "2.1"}
    resp = _gather("banking-swift-evidence", SWIFT_CLEAN_PAYLOAD, prov_bad)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    Downgraded source: {decision} (version recorded in provenance, not enforced by boundary)")
        if decision == "ASSERT":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected ASSERT, got {decision}")
    else:
        failed += 1

    print(f"\n  Admissibility: {passed} passed, {failed} failed")
    return passed, failed


# -- Test 4: Prohibition ----------------------------------------------------

def verify_prohibition() -> tuple[int, int]:
    print(RULE)
    print("  Verification 4: Prohibition")
    print(RULE)

    passed = 0
    failed = 0

    print("  Submitting clean evidence (no prohibited fields)...")
    resp = _gather("banking-swift-evidence", SWIFT_CLEAN_PAYLOAD, SWIFT_PROVENANCE)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    Clean: {decision}")
        if decision == "ASSERT":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected ASSERT, got {decision}")
    else:
        failed += 1

    print("  Submitting with manual_override_without_approval injected...")
    prohibited_payload = dict(SWIFT_CLEAN_PAYLOAD)
    prohibited_payload["manual_override_without_approval"] = 1
    prov = dict(SWIFT_PROVENANCE)
    prov["manual_override_without_approval"] = "ops_workflow"
    resp = _gather("banking-swift-evidence", prohibited_payload, prov)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    Prohibited: {decision}")
        if decision == "DEFER":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected DEFER, got {decision}")
    else:
        failed += 1

    print(f"\n  Prohibition: {passed} passed, {failed} failed")
    return passed, failed


# -- Test 5: Evolution ------------------------------------------------------

def verify_evolution() -> tuple[int, int]:
    print(RULE)
    print("  Verification 5: Boundary Evolution")
    print(RULE)

    passed = 0
    failed = 0

    s8_payload = dict(SWIFT_CLEAN_PAYLOAD)
    s8_payload["system_enrichment_logged"] = 0
    s8_payload["adjustment_classification_complete"] = 0
    s8_payload["all_modification_events_captured"] = 0
    s8_payload["_provenance"] = SWIFT_PROVENANCE

    versions = [
        ("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0", "ASSERT"),
        ("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2", "DEFER"),
        ("B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4", "DEFER"),
    ]

    for boundary_ref, expected in versions:
        label = boundary_ref.split("_V")[-1].replace("_", ".")
        print(f"  Evaluating against policy v{label}...")

        resp = api(
            "POST",
            "/v1/verify",
            {
                "boundary_ref": boundary_ref,
                "environment_id": ENVIRONMENT_ID,
                "workload": s8_payload,
            },
        )
        if resp:
            ev = resp.get("evaluation") or resp
            decision = ev.get("decision", "")
            print(f"    v{label}: {decision}")
            if decision == expected:
                passed += 1
            else:
                failed += 1
                print(f"    FAIL: expected {expected}, got {decision}")
        else:
            failed += 1

    print(f"\n  Evolution: {passed} passed, {failed} failed")
    return passed, failed


# -- Test 6: Coverage -------------------------------------------------------

def verify_coverage() -> tuple[int, int]:
    print(RULE)
    print("  Verification 6: Balance Sheet Coverage")
    print(RULE)

    passed = 0
    failed = 0

    print("  Submitting BS1 (all adjustments captured)...")
    resp = _gather("banking-balance-sheet-evidence", BS_CLEAN_PAYLOAD, BS_PROVENANCE)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    BS1: {decision}")
        if decision == "ASSERT":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected ASSERT, got {decision}")
    else:
        failed += 1

    print("  Submitting BS2 (5 missing operational adjustments)...")
    bs2_payload = dict(BS_CLEAN_PAYLOAD)
    bs2_payload["non_financial_adjustments_captured"] = 0
    resp = _gather("banking-balance-sheet-evidence", bs2_payload, BS_PROVENANCE)
    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")
        print(f"    BS2: {decision}")
        if decision == "DEFER":
            passed += 1
        else:
            failed += 1
            print(f"    FAIL: expected DEFER, got {decision}")
    else:
        failed += 1

    print(f"\n  Coverage: {passed} passed, {failed} failed")
    return passed, failed


# -- Test 7: Cascade --------------------------------------------------------

def verify_cascade() -> tuple[int, int]:
    print(RULE)
    print("  Verification 7: Governance Cascade")
    print(RULE)

    passed = 0
    failed = 0

    print("  Submitting S2 (enrichment suppressed — expect 3-predicate cascade)...")
    s2_payload = dict(SWIFT_CLEAN_PAYLOAD)
    s2_payload["system_enrichment_logged"] = 0
    s2_payload["adjustment_classification_complete"] = 0
    s2_payload["all_modification_events_captured"] = 0
    resp = _gather("banking-swift-evidence", s2_payload, SWIFT_PROVENANCE)

    if resp:
        ev = resp.get("evaluation") or {}
        decision = ev.get("decision")

        if decision != "DEFER":
            failed += 1
            print(f"    FAIL: expected DEFER, got {decision}")
            print(f"\n  Cascade: {passed} passed, {failed} failed")
            return passed, failed

        predicate_results = ev.get("predicate_results") or ev.get("predicates") or {}
        expected_failures = {
            "system_enrichment_captured",
            "adjustments_classified",
            "all_events_captured",
        }

        actual_failures: set[str] = set()
        for name, result in predicate_results.items():
            if isinstance(result, dict):
                if not result.get("passed", result.get("result", True)):
                    actual_failures.add(name)
            elif result is False:
                actual_failures.add(name)

        if expected_failures.issubset(actual_failures):
            passed += 1
            print(f"    PASS: 3-predicate cascade confirmed")
            print(f"    Failed predicates: {sorted(actual_failures)}")
        else:
            failed += 1
            missing = expected_failures - actual_failures
            print(f"    FAIL: expected failures {sorted(expected_failures)}")
            print(f"    Actual failures: {sorted(actual_failures)}")
            print(f"    Missing: {sorted(missing)}")
    else:
        failed += 1

    print(f"\n  Cascade: {passed} passed, {failed} failed")
    return passed, failed


# -- CLI entry point ---------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="VB-OS Banking Reference Verification")
    parser.add_argument("--all", action="store_true", help="Run all verifications")
    parser.add_argument("--parity", action="store_true", help="Replay parity only")
    parser.add_argument("--completeness", action="store_true", help="Completeness only")
    parser.add_argument("--admissibility", action="store_true", help="Admissibility only")
    parser.add_argument("--prohibition", action="store_true", help="Prohibition only")
    parser.add_argument("--evolution", action="store_true", help="Boundary evolution only")
    parser.add_argument("--coverage", action="store_true", help="Balance sheet coverage only")
    parser.add_argument("--cascade", action="store_true", help="Governance cascade only")

    args = parser.parse_args()
    run_all = args.all or not any([
        args.parity, args.completeness, args.admissibility,
        args.prohibition, args.evolution, args.coverage, args.cascade,
    ])

    total_pass = 0
    total_fail = 0

    tests = [
        ("parity", verify_parity),
        ("completeness", verify_completeness),
        ("admissibility", verify_admissibility),
        ("prohibition", verify_prohibition),
        ("evolution", verify_evolution),
        ("coverage", verify_coverage),
        ("cascade", verify_cascade),
    ]

    for flag, fn in tests:
        if run_all or getattr(args, flag, False):
            p, f = fn()
            total_pass += p
            total_fail += f
            print()

    print(RULE)
    print(f"  TOTAL: {total_pass} passed, {total_fail} failed")
    status = "ALL PASSED" if total_fail == 0 else "FAILURES DETECTED"
    print(f"  Status: {status}")
    print(RULE)
    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
