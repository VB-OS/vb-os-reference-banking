# VB-OS Banking Reference Integration -- Setup Guide

**Author:** [Asaad Riaz](https://github.com/anriaz) -- Founder, MNC Labs, Inc.
**Repository:** [github.com/VB-OS/vb-os-reference-banking](https://github.com/VB-OS/vb-os-reference-banking)
**Platform:** [VB-OS Cloud](https://vbos.cloud)

---

Complete setup and execution guide for the banking operational completeness
certification pipeline. Covers SWIFT adjustment integrity and balance sheet
adjustment certification -- both evaluated by VB-OS Cloud with evidence pushed
from a local banking database via caller-supplied payload.

---

## Prerequisites

- **Python 3.11+**
- **Docker Desktop** (running)
- **Git**

No external trading accounts or live API keys are needed. This integration
demonstrates operational completeness certification -- all evidence is derived
from the local banking database.

---

## Part 1: VB-OS Cloud Setup

### 1.1 Log in to the VB-OS Console

Open https://vbos.cloud and sign in.

### 1.2 Fork the Banking Operational Certification template

1. In the sidebar, click **Registry**.
2. Find **"Banking Operational Certification"**.
3. Click **Fork Template** and give the project a name (e.g. "Banking Certification Evaluation").

This creates a fully provisioned project with:
- 5 boundaries (3 SWIFT policy versions + 2 Balance Sheet versions) -- approved and deployed
- 2 connectors -- pre-configured with evidence mappings and provenance requirements
- 2 governance flows -- approved, active, and deployed
- 2 certification models

### 1.3 Copy the Project ID and Environment ID

Inside the new project:

1. Go to **Settings** (in the project sub-navigation). Under the **General**
   tab, copy the **Project ID**.
2. Switch to the **Environments** tab. Copy the **Environment ID** for the
   "Development" environment created by the fork.

You will need both in your `.env` file.

### 1.4 Create an API key

Inside the project, go to **Integrate** and select the **API Keys** tab.
Select the environment from the dropdown, then click **Create Key**.

**Select all scopes.** This is a reference integration that exercises the
full platform surface -- boundaries, connectors, flows, evaluations,
certifications, and replay. Copy the key immediately; it is shown only once.

---

## Part 2: Local Environment Setup

### 2.1 Clone and enter the repository

```bash
git clone https://github.com/VB-OS/vb-os-reference-banking.git
cd vb-os-reference-banking
```

### 2.2 Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install vendor/vb_os-0.1.0.tar.gz
```

This creates an isolated Python environment, installs pinned dependencies
(psycopg2 for PostgreSQL access), and installs the VB-OS Python SDK from
the vendored distribution. `demo.py` uses the SDK; all other scripts
(`bootstrap.py`, `verify.py`) use the standard library only.

Every time you open a new terminal to run scripts, activate the environment
first:

```bash
source .venv/bin/activate
```

### 2.3 Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the three values from Part 1:

```
VBOS_URL=https://api.vb-os.org
VBOS_API_KEY=<your API key from step 1.4>
VBOS_PROJECT_ID=<your project ID from step 1.3>
VBOS_ENVIRONMENT_ID=<your environment ID from step 1.3>
```

Leave all other values at their defaults -- they configure the local
PostgreSQL database that ships with this repository.

### 2.4 Start the local source systems

```bash
docker compose up -d
```

This starts one container:
- **PostgreSQL** (banking database) at `localhost:5432` -- user `banking`, database `banking`

The PostgreSQL container is seeded automatically from `seed.sql` on first start,
creating the schema (operational_events, evidence_state, source_versions,
adjustment_coverage, missing_adjustments, certification_scope) and all 13
scenario datasets.

Verify it is running:

```bash
docker compose ps
```

It should show `running` (healthy) status.

### 2.5 Verify the setup

At this point, everything is ready:

- **VB-OS Cloud** has your project with 5 boundaries, 2 connectors, 2 flows,
  and 2 certification models -- all provisioned by the template fork.
- **Local source systems** (PostgreSQL) are running with seeded data for all
  13 scenarios.
- **Environment variables** are set in `.env`.

---

## Part 3: Run the Integration

All commands below require the environment to be exported:

```bash
set -a; source .env; set +a
```

### 3.1 List available scenarios

```bash
python3 demo.py --list
```

Shows all 13 scenarios: 8 SWIFT adjustment integrity (S1-S8) and 5 balance
sheet certification (BS1-BS5).

### 3.2 Run individual scenarios

```bash
python3 demo.py --scenario S1     # SWIFT: Clean -> CERTIFIED
python3 demo.py --scenario S2     # SWIFT: Enrichment missing -> NOT CERTIFIED (cascade)
python3 demo.py --scenario S3     # SWIFT: Prohibited evidence -> NOT CERTIFIED
python3 demo.py --scenario BS2    # Balance Sheet: 5 missing adjustments -> NOT CERTIFIED
```

Each scenario reads the evidence state from the local PostgreSQL database,
derives evidence, and submits the payload to VB-OS Cloud. VB-OS extracts
evidence, validates provenance, evaluates the boundary, and returns the
decision with predicate results and lineage.

### 3.3 Run all scenarios

```bash
python3 demo.py --all
```

Runs all 13 scenarios in sequence and reports the certification outcomes.

### 3.4 Run with governance cascade

```bash
python3 demo.py --scenario S2 --cascade
```

Shows the governance cascade for scenario S2: one suppressed event (EVT-005
System Auto-Enrichment) produces three failed conditions through the
dependency chain: enrichment not captured -> classification incomplete ->
events not captured -> certification withheld.

### 3.5 Run boundary evolution

```bash
python3 demo.py --scenario S8 --evolution
```

Evaluates the same evidence against three SWIFT policy versions:
- v1.0 (7 predicates): **CERTIFIED** -- does not require enrichment
- v1.2 (8 predicates): **NOT CERTIFIED** -- enrichment now required
- v1.4 (10 predicates): **NOT CERTIFIED** -- cascading failure

Proves the gap was always there; the policy just did not require it.

### 3.6 Show adjustment coverage panel

```bash
python3 demo.py --scenario BS2 --coverage
```

Shows the balance sheet coverage panel:
- Financial adjustments: 38,109 / 38,109 (100.0%)
- Operational adjustments: 3,114 / 3,119 (99.84%)
- 5 missing adjustments from Singapore Treasury and LATAM Shared Services
- Traditional Reconciliation Controls: PASS
- VB-OS Operational Completeness: NOT CERTIFIED

### 3.7 Run mutation scenarios

```bash
python3 demo.py --mutations
```

Runs the three mutation scenarios back-to-back:
- **S3** (Prohibition): Inject manual_override_without_approval -- all 10
  evidence fields are 1, but prohibited evidence exists
- **S4** (Admissibility): Downgrade recon_engine to v2.1 -- evidence is
  present but from an untrusted source version
- **S5** (All three): Suppressed event + prohibited evidence + downgraded
  source -- three distinct failure classes in one certification

---

## Part 4: Verify Results on the Platform

After running the demo scenarios, open the VB-OS Console at
https://vbos.cloud to see what the platform recorded. Sign in and
navigate to the project you created in Part 1.

### Overview

The project landing page shows a summary of recent activity: total
evaluations, ASSERT/DEFER split, and boundary health. After running
`--all`, you should see evaluations for both SWIFT and Balance Sheet
boundaries.

### Monitor

Click **Monitor** in the project sub-navigation. This is the live
evaluation feed. Each row shows:

- **Decision** -- ASSERT (green) or DEFER (amber)
- **Boundary** -- which boundary was evaluated
- **Timestamp** -- when the evaluation occurred
- **Acquisition class** -- `caller_supplied_payload` for both connectors

You should see entries for every scenario you ran. ASSERT results
confirm the workload passed all predicates. DEFER results show which
predicate failed.

### Evaluation Detail

Click any evaluation row to open the detail view. This shows:

- **Evidence** -- the exact evidence fields VB-OS extracted from the
  raw payload (enrichment status, classification status, etc.)
- **Predicate results** -- each named predicate and whether it passed
  or failed
- **Provenance** -- how the evidence was acquired (connector ID,
  acquisition class, source system, version, timestamp)
- **Failure reasons** -- for DEFER results, the specific predicate
  that failed or the prohibition that was violated

### Replay

From the evaluation detail view, click **Replay**. VB-OS re-evaluates
the same input artifact against the same boundary snapshot and binary
version. The replay result must match the original. This proves
deterministic reproducibility: given the same artifact, boundary, and
binary, the result is identical.

The replay view shows:

- **Original decision** and **Replay decision** -- these must match
- **Identity match** -- confirms the same binary and boundary snapshot
  were used
- **Input hash** -- proves the input artifact has not been modified

### What to Expect

| Scenario | Boundary | Expected Decision | What to Look For |
|----------|----------|-------------------|------------------|
| S1 | B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4 | ASSERT | All 10 predicates pass |
| S2 | B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4 | DEFER | 3 predicates fail (enrichment cascade) |
| S3 | B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4 | DEFER | `manual_override_without_approval` prohibition |
| S4 | B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4 | DEFER | Provenance: recon_engine v2.1 inadmissible |
| S6 | B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4 | DEFER | `dual_auth_complete` fails |
| BS1 | B_BALANCE_SHEET_CERTIFICATION | ASSERT | All 8 predicates pass |
| BS2 | B_BALANCE_SHEET_CERTIFICATION | DEFER | `non_financial_captured` fails (5 missing) |

---

## Part 5: Verification Suite

```bash
python3 verify.py --all
```

Seven deterministic verification tests that prove the governance pipeline
is working correctly. No external services needed beyond VB-OS Cloud.

| Test | Proves |
|------|--------|
| `--parity` | Replay every sealed evaluation, confirm decision parity |
| `--completeness` | S1 ASSERT, suppress EVT-005, DEFER (deterministic cascade) |
| `--admissibility` | S1 with recon_engine v2.3 ASSERT, downgrade to v2.1 DEFER |
| `--prohibition` | S1 ASSERT, inject manual_override, DEFER |
| `--evolution` | Same evidence against v1.0/v1.2/v1.4: ASSERT/DEFER/DEFER |
| `--coverage` | BS1 ASSERT (41,228/41,228), BS2 DEFER (41,223/41,228, 5 missing) |
| `--cascade` | S2: 1 suppressed event, 3-predicate failure chain verified |

Run individual tests:

```bash
python3 verify.py --parity
python3 verify.py --completeness
python3 verify.py --admissibility
python3 verify.py --prohibition
python3 verify.py --evolution
python3 verify.py --coverage
python3 verify.py --cascade
```

---

## Part 6: Running with Docker (Alternative)

Instead of installing Python and the SDK locally, you can run all scripts
inside a container. This requires only Docker Desktop and a configured `.env`
file (Parts 1 and 2.3).

### 6.1 Start source systems and build the app image

```bash
docker compose --profile app build
docker compose up -d
```

The first command builds the integration container image. The second starts
PostgreSQL. The health check ensures PostgreSQL is ready before any app
commands run.

### 6.2 Run scenarios

```bash
docker compose --profile app run --rm banking-app demo.py --list
docker compose --profile app run --rm banking-app demo.py --scenario S1
docker compose --profile app run --rm banking-app demo.py --all
```

### 6.3 Run with governance cascade

```bash
docker compose --profile app run --rm banking-app demo.py --scenario S2 --cascade
```

### 6.4 Run boundary evolution

```bash
docker compose --profile app run --rm banking-app demo.py --scenario S8 --evolution
```

### 6.5 Run coverage panel

```bash
docker compose --profile app run --rm banking-app demo.py --scenario BS2 --coverage
```

### 6.6 Run verification suite

```bash
docker compose --profile app run --rm banking-app verify.py --all
```

### 6.7 Stop everything

```bash
docker compose --profile app down
```

---

## What Each Script Does

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `demo.py` | Runs individual scenarios, governance cascades, boundary evolution, coverage analysis, and mutation demonstrations | `vbos` SDK (vendored in `vendor/`) |
| `verify.py` | Seven deterministic verification tests | Standard library only |
| `bootstrap.py` | (Optional) Standalone provisioning of boundaries, connectors, flows, and certifications -- use if not forking the template | Standard library only |
| `seed_template.py` | (Admin) Register template in the platform template registry | `asyncpg` |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VBOS_URL` | Yes | VB-OS Cloud API URL. Default: `https://api.vb-os.org` |
| `VBOS_API_KEY` | Yes | API key from Part 1, step 1.4 |
| `VBOS_PROJECT_ID` | Yes | Project ID from Part 1, step 1.3 |
| `VBOS_ENVIRONMENT_ID` | Yes | Environment ID from Part 1, step 1.3 |
| `DATABASE_URL` | No | PostgreSQL connection string. Default: `postgresql://banking:banking@banking-postgres:5432/banking` |

---

## Acquisition Mode

Both connectors use **caller-supplied payload**: the local scripts read from
the banking database (operational events, evidence state, source versions,
adjustment coverage), build evidence, and push it to VB-OS Cloud. VB-OS
extracts evidence, validates provenance, evaluates the boundary, and records
the full lineage. The platform never touches the source system directly.

---

## Boundary DSL Source

The five boundary definitions live in `boundaries/` as VB-OS DSL source files:

| File | Boundary | Predicates | Policy |
|------|----------|------------|--------|
| `B_SWIFT_ADJUSTMENT_INTEGRITY_V1_0.dsl` | SWIFT core fields | 7 | v1.0 (2024-Q1) |
| `B_SWIFT_ADJUSTMENT_INTEGRITY_V1_2.dsl` | SWIFT + enrichment | 8 | v1.2 (2024-Q3) |
| `B_SWIFT_ADJUSTMENT_INTEGRITY_V1_4.dsl` | SWIFT + classification + events | 10 | v1.4 (2025-Q1, current) |
| `B_BALANCE_SHEET_CERTIFICATION.dsl` | Multi-entity consolidation | 8 | v1.0 (current) |
| `B_BALANCE_SHEET_CERTIFICATION_V0_9.dsl` | Original consolidation | 6 | v0.9 (original) |

These are the source of truth. `bootstrap.py` syncs them to VB-OS Cloud on
every run.

---

## Troubleshooting

**demo.py fails with "HTTP 401"**
Your API key is invalid or expired. Create a new one under **Integrate >
API Keys** (step 1.4).

**demo.py fails with "HTTP 403"**
The API key is missing required scopes. Delete it and create a new one with
all scopes selected.

**"Connector 'banking-swift-evidence' not found"**
The template fork should have created both connectors. Check your project
under **Integrate > Connectors**. If connectors are missing, re-fork the
template.

**PostgreSQL connection refused**
The banking database runs inside Docker. Check `docker compose ps`. If not
running: `docker compose up -d`. The database is seeded automatically from
`seed.sql` on first start.
