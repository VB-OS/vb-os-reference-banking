# VB-OS Banking Reference Integration

**Author:** [Asaad Riaz](https://github.com/anriaz) -- Founder, MNC Labs, Inc.
**Platform:** [VB-OS Cloud](https://vbos.cloud) | [Documentation](https://vb-os.org) | [GitHub](https://github.com/VB-OS)

---

A reference implementation demonstrating deterministic operational completeness
certification for banking workflows through [VB-OS Cloud](https://vbos.cloud),
the verification-as-a-service platform built by [MNC Labs](https://mnclabs.com).
This integration exercises two domain models -- SWIFT adjustment integrity
(cross-border wire transfers, 2.4M transactions) and balance sheet adjustment
certification (multi-entity consolidation, 41,228 adjustments) -- with three
failure classes, governance cascades, boundary evolution, and the "Traditional
PASS / VB-OS NOT CERTIFIED" differentiation that proves operational completeness
is a category of certification that did not exist before VB-OS.

VB-OS holds no banking or certification authority. It verifies provenance, not
truth: was this evidence submitted, from what source, at what version, and does
it satisfy the governance boundary. The evaluation engine is integer-only,
deterministic, and replay-safe -- the same input artifact, boundary snapshot,
and binary version always produce the same decision.

## Quick Start

See [SETUP.md](SETUP.md) for complete setup instructions -- from forking the
template in VB-OS Cloud to running the full integration locally.

### Docker (recommended)

After completing VB-OS Cloud setup (SETUP.md Part 1) and creating your `.env`:

```bash
docker compose --profile app build
docker compose up -d
docker compose --profile app run --rm banking-app demo.py --all
```

No local Python installation required. See SETUP.md Part 6 for details.

## Architecture

```
Source Systems (PostgreSQL)
    |
    v
[Evidence Derivation] --> Build evidence from operational events
    |
    v
[VB-OS Cloud]
    ├── Connector: evidence acquisition + provenance validation
    ├── Governance Flow: evaluation routing + escalation
    ├── Binary Evaluation: boundary predicates (deterministic)
    └── Sealed Record: full lineage, replay-safe
    |
    v
Certification Decision (ASSERT / DEFER)
    |
    v
Certification Label (CERTIFIED / NOT CERTIFIED — class)
```

## Acquisition Mode

Both connectors use **caller-supplied payload**: the local scripts read from
the banking database (operational events, evidence state, source versions,
adjustment coverage), build evidence, and push it to VB-OS Cloud. VB-OS
extracts evidence, evaluates the boundary, and records the provenance. The
platform never touches the source system directly.

## Boundaries

| Boundary | Predicates | Purpose |
|----------|-----------|---------|
| B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4 | 10 | SWIFT wire transfer operational completeness (current policy) |
| B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2 | 8 | SWIFT operational completeness (enrichment requirement added) |
| B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0 | 7 | SWIFT operational completeness (core fields only) |
| B_BALANCE_SHEET_CERTIFICATION | 8 | Multi-entity balance sheet consolidation |
| B_BALANCE_SHEET_CERTIFICATION_V0_9 | 6 | Balance sheet consolidation (original policy) |

## Scenarios

### SWIFT Adjustment Integrity (S1-S8)

| Scenario | Description | Decision | Certification Label |
|----------|-------------|----------|-------------------|
| S1 | All events active, all sources compliant | ASSERT | CERTIFIED |
| S2 | EVT-005 suppressed (enrichment missing) | DEFER | NOT CERTIFIED -- INCOMPLETE (3 conditions, cascade) |
| S3 | All events active + prohibited evidence injected | DEFER | NOT CERTIFIED -- PROHIBITED OPERATION |
| S4 | All events active + recon_engine downgraded to v2.1 | DEFER | NOT CERTIFIED -- INADMISSIBLE EVIDENCE |
| S5 | EVT-005 suppressed + prohibited + downgraded | DEFER | NOT CERTIFIED -- MULTIPLE VIOLATIONS |
| S6 | Dual authorization missing (EVT-006 suppressed) | DEFER | NOT CERTIFIED -- INCOMPLETE (single condition) |
| S7 | All events active, compliance_engine v3.8 | DEFER | NOT CERTIFIED -- INADMISSIBLE EVIDENCE |
| S8 | Boundary evolution (same evidence, three policies) | ASSERT/DEFER/DEFER | CERTIFIED / NOT CERTIFIED / NOT CERTIFIED |

### Balance Sheet Certification (BS1-BS5)

| Scenario | Description | Decision | Certification Label |
|----------|-------------|----------|-------------------|
| BS1 | All events active, all adjustments captured | ASSERT | CERTIFIED |
| BS2 | 5 missing operational adjustments (Traditional: PASS) | DEFER | NOT CERTIFIED -- INCOMPLETE |
| BS3 | Missing adjustments + unreviewed manual journal entry | DEFER | NOT CERTIFIED -- MULTIPLE VIOLATIONS |
| BS4 | Boundary evolution (v0.9 passes, v1.0 fails) | ASSERT/DEFER | CERTIFIED / NOT CERTIFIED |
| BS5 | Non-financial adjustments not captured | DEFER | NOT CERTIFIED -- INCOMPLETE (operational gap) |

Run `python3 demo.py --list` for descriptions, or `python3 demo.py --all` to
run all 13 scenarios.

## Three Failure Classes

| Class | Meaning | Example |
|-------|---------|---------|
| Completeness | Required evidence missing | EVT-005 suppressed -- 3 conditions fail in cascade |
| Admissibility | Evidence from untrusted source version | recon_engine v2.1 vs required v2.3 |
| Prohibition | Evidence exists that must NOT exist | manual_override_without_approval injected |

Traditional reconciliation tools check one dimension: do the numbers match?
VB-OS checks three: is the evidence complete, is it admissible, and is there
evidence that should not exist? A reconciliation that says PASS may be hiding
suppressed events, unclassified adjustments, and unauthorized overrides.

## Governance Cascade

One suppressed event produces a chain reaction through the certification model:

```
EVT-005 suppressed (System Auto-Enrichment)
    → system_enrichment_logged = 0        (predicate fails)
    → adjustment_classification_complete = 0  (cannot classify without enrichment)
    → all_modification_events_captured = 0    (cannot verify completeness)
    → 3 failed predicates → DEFER → NOT CERTIFIED -- INCOMPLETE
```

Run `demo.py --scenario S2 --cascade` to see the full cascade trace.

## Boundary Evolution

Same evidence evaluated against progressively stricter policy versions:

| Policy | Predicates | Result | Why |
|--------|-----------|--------|-----|
| v1.0 (2024-Q1) | 7 | CERTIFIED | Does not require enrichment evidence |
| v1.2 (2024-Q3) | 8 | NOT CERTIFIED | Enrichment now required, EVT-005 suppressed |
| v1.4 (2025-Q1) | 10 | NOT CERTIFIED | Cascading failure through classification |

The gap was always there -- the policy just did not catch it until v1.2. Run
`demo.py --scenario S8 --evolution` to see the evolution trace.

## Verification Suite

`verify.py` contains seven deterministic verification tests:

| Test | Proves |
|------|--------|
| Parity | Replay every sealed evaluation, confirm decision parity |
| Completeness | S1 ASSERT, suppress EVT-005, DEFER (deterministic cascade) |
| Admissibility | S1 with recon_engine v2.3 ASSERT, downgrade to v2.1 DEFER |
| Prohibition | S1 ASSERT, inject manual_override, DEFER |
| Evolution | Same evidence against v1.0/v1.2/v1.4: ASSERT/DEFER/DEFER |
| Coverage | BS1 ASSERT (41,228/41,228), BS2 DEFER (41,223/41,228, 5 missing) |
| Cascade | S2: 1 suppressed event, 3-predicate failure chain verified |

## Directory Structure

```
vb-os-reference-banking/
├── README.md               # This file
├── SETUP.md                # Complete setup guide
├── LICENSE                 # Apache 2.0
├── Dockerfile              # Container image for integration scripts
├── docker-compose.yml      # PostgreSQL + app container
├── requirements.txt        # Pinned Python dependencies
├── manifest.json           # Machine-readable integration metadata
├── .env.example            # Environment variable template
├── demo.py                 # Scenario runner (--scenario, --all, --cascade, --evolution, --coverage, --mutations)
├── verify.py               # Deterministic verification suite (7 tests)
├── bootstrap.py            # (Optional) Standalone VB-OS provisioning
├── seed_template.py        # (Admin) Register template in template registry
├── seed.sql                # PostgreSQL schema and seed data for all 13 scenarios
├── boundaries/             # VB-OS DSL boundary definitions (VBL v2)
│   ├── B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0.dsl
│   ├── B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2.dsl
│   ├── B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4.dsl
│   ├── B_BALANCE_SHEET_CERTIFICATION.dsl
│   └── B_BALANCE_SHEET_CERTIFICATION_V0_9.dsl
└── vendor/                 # Vendored VB-OS Python SDK (not yet on PyPI)
    └── vb_os-0.1.0.tar.gz
```

## About VB-OS

[VB-OS](https://vbos.cloud) is a verification-as-a-service platform that
provides deterministic, auditable governance for regulated workflows. Built by
[MNC Labs, Inc.](https://mnclabs.com), VB-OS evaluates evidence against
boundary definitions using an integer-only Rust binary, producing sealed
evaluation records with full provenance and replay determinism.

The platform supports any domain where decisions must be verifiable after the
fact: financial trading, healthcare credentialing, supply chain compliance,
banking operational certification, and autonomous agent governance.

- **Console:** [vbos.cloud](https://vbos.cloud)
- **API:** [api.vb-os.org](https://api.vb-os.org)
- **Documentation:** [vb-os.org](https://vb-os.org)
- **GitHub:** [github.com/VB-OS](https://github.com/VB-OS)

## License

Copyright 2026 MNC Labs, Inc. All rights reserved.

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for
the full text.
