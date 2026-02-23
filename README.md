# Rearc Quest — Data Pipeline Project

## Description

This project was created by reading through the entire Rearc quest document and implementing it end-to-end. The goal was to **republish source data to S3**, load it into Databricks following a **medallion architecture**, perform **data analysis**, and automate the process with a **data pipeline** (BrickFlow).

---

## Tech Stack

| Layer        | Technology                          |
|-------------|-------------------------------------|
| Language    | **Python**                          |
| Processing  | **PySpark** / **Spark SQL**         |
| Platform    | **Databricks**                      |
| Cloud       | **AWS** (S3, and optionally IAM, SQS, Lambda) |
| Orchestration | **BrickFlow** — CLI for Python-based Databricks Workflows |

[BrickFlow](https://engineering.nike.com/brickflow/v1.3.1/) is a declarative, code-first way to define and deploy Databricks workflows (powered by Databricks Asset Bundles / Terraform).

---

## Architecture

- **Medallion architecture**: Bronze (raw) → Silver (cleansed) → Gold (analytics/views).
- **Source of truth**: Data is first published to **S3**, then copied into Databricks as managed Delta tables.
- **Pipeline**: Single BrickFlow workflow that chains: republish to S3 → load bronze → load silver → data analysis (gold). Retries and email notifications are configured in the workflow.

### Data Flow

```
BLS / DataUSA APIs  →  S3 (source of truth)
                            ↓
                      Databricks Bronze (raw copy)
                            ↓
                      Databricks Silver (cleansed)
                            ↓
                      Databricks Gold (views / reports)
```

### S3 Location (Republished Data)

- **BLS**: `s3://kbannu-test1/bls/pr/pub/time.series/pr/`
- **DataUSA**: `s3://kbannu-test1/datausa/acs_yg_total_population_1.json`

---

## Thought Process by Step

### Step 1 — Republish Data to S3 and Load to Databricks

**Requirement:** Republish source data to S3.

**Options considered for storing/using that data on Databricks:**

1. Use S3 only (as in the assignment).
2. Query S3 directly from Databricks (external table or direct path).
3. Create an external table pointing to S3.
4. Use Volumes to copy data into Databricks.

**Choice:** Publish to S3 (source of truth) and **copy into Databricks as managed tables** (bronze layer).

**Reasons:**

- S3 remains the single source of truth.
- Current design overwrites; later you can switch to **append** with retention for history.
- Aligns with medallion architecture — this raw copy is the **bronze** layer.

**Issues encountered:** On the free tier of Databricks and S3, direct S3 access from Databricks was not fully available. Workaround: use **AWS access key and secret** (stored in Databricks Secrets) for S3 uploads from sync scripts. In a licensed setup, alternatives would be: IAM role attached to the cluster, or tagging buckets and using Databricks Secrets / Cerberus for credentials.

---

### Step 2 — Second Dataset

The same pattern was applied: data published to S3 first, then copied into Databricks (bronze).

---

### Step 3 — Data Analysis

- Tables were already in the **bronze** layer.
- While querying in a notebook, **data cleansing** was needed (especially for CSVs), which led to a dedicated **silver** layer: clean, typed, deduplicated data.
- **Gold** layer: business logic implemented as Spark SQL views (e.g. population stats, best year per series, series–population report) for analysis or dashboards.
- Validation was done by copying data from S3 to local/volume and running the same queries in notebooks to verify results.

---

### Step 4 — Automated Data Pipeline

**Options considered:**

1. Manually create a workflow in the Databricks UI and schedule it.
2. **Delta Live Tables (DLT)**.
3. Integrate **Airflow** with Databricks.
4. **BrickFlow** — Python-based, declarative Databricks Workflows.

**Choice:** **BrickFlow.**

**Reasons:**

- Keep storage, compute, and orchestration in one ecosystem (Databricks + BrickFlow).
- Declarative Python workflows — easy to read and maintain.
- Task dependencies and **workflow-level dependencies** (beyond what’s native in the UI).
- Reuse of code and less redundancy.
- Retries and email notifications are configured in code.
- Workflow permissions (e.g. who can manage or read) are defined in the workflow.

**Note on execution:** The pipeline was validated locally (structure and task graph). On the free Databricks tier, job cluster / serverless constraints prevented installing all packages for a full run; the workflow definition and screenshot of the pipeline in the UI confirm the DAG and settings.

**Additional assignment ideas (SQS + Lambda):**  
To trigger reports (e.g. from Part 3) when a message lands in SQS, you could: (1) maintain a **logs table** with timestamps and have a downstream task run only when the table is updated, or (2) split into separate jobs and use a trigger condition (e.g. table populated) to start the report job. BrickFlow can orchestrate Databricks steps; SQS/Lambda would be separate AWS components that could call Databricks or read from the same tables.

**Data quality:** Frameworks like **DLT expectations** or **spark-expectations** (e.g. Nike’s) can be added for validation in the pipeline.

---

## Project Structure

```
rearc/
├── README.md                           # This file
├── docs/
│   ├── BRICKFLOW_LOCAL_DEPLOY.md       # How to deploy workflow locally
│   └── DATABRICKS_SECRETS.md           # S3 credentials in Databricks Secrets
├── products/rearc/
│   ├── pyproject.toml                  # Python deps (Poetry): brickflows, boto3, requests, beautifulsoup4
│   ├── bundle.yml                      # BrickFlow / Databricks bundle (e.g. rearc-local)
│   ├── workflows/
│   │   ├── rearc_quest_workflow.py     # Main BrickFlow workflow definition
│   │   └── entrypoint.py               # Task entrypoint used by BrickFlow
│   └── spark/python/src/
│       ├── etl/
│       │   ├── bls_sync.py             # Republish BLS data to S3
│       │   └── datausa_population_sync.py  # Republish DataUSA population to S3
│       └── notebooks/
│           ├── load_bronze_layer.ipynb # S3 → Bronze (managed Delta tables)
│           ├── load_silver_layer.ipynb # Bronze → Silver (cleansed)
│           └── data_analysis_gold_layer.ipynb # Silver → Gold (views/reports)
```

- **Workflow:** `start` → `bls_sync` & `datausa_population_sync` (parallel) → `load_bronze_layer` → `load_silver_layer` → `data_analysis` → `end`.
- Tasks use **notebook tasks** (notebooks) or **Python tasks** (e.g. `etl/bls_sync`, `etl/datausa_population_sync`).
- **Permissions** and **email notifications** (on start / success / failure) are set in the workflow.

---

## Running and Deploying

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) (or install deps from `pyproject.toml` manually)
- Databricks CLI configured (for bundle deploy)
- AWS credentials or Databricks secrets for S3 (e.g. `quest-aws` scope with `access-key-id` and `secret-access-key`)

### Setup from scratch

From the project root or `products/rearc`:

```bash
# Virtual environment
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

# Databricks CLI and auth
pip3 install databricks-cli
databricks configure --token
# When prompted:
#   Databricks host: https://dbc-1e2044e7-1d5b.cloud.databricks.com/
#   Token: <your personal access token>

# BrickFlow and project tooling
pip3 install brickflows
pip3 install poetry
# Optional: pip3 install make   # if you use Makefile targets
```

Then install project dependencies with Poetry:

```bash
cd products/rearc
poetry install
```

### Create AWS secrets in Databricks (for S3 access)

Run once so ETL tasks can upload to S3 from Databricks:

```bash
databricks secrets create-scope --scope quest-aws
databricks secrets put --scope quest-aws --key access-key-id --string-value "YOUR_AWS_ACCESS_KEY_ID"
databricks secrets put --scope quest-aws --key secret-access-key --string-value "YOUR_AWS_SECRET_ACCESS_KEY"
```

Replace the placeholder values with your AWS credentials. See [Databricks secrets](docs/DATABRICKS_SECRETS.md) for details.

### Install (if already set up)

```bash
cd products/rearc
poetry install
```

### BrickFlow — Local / Dev Deploy

- Use BrickFlow CLI to deploy to a target (e.g. `rearc-local`). See:
  - [BrickFlow local deploy](docs/BRICKFLOW_LOCAL_DEPLOY.md) — how to deploy and validate the pipeline locally.
  - [Databricks secrets](docs/DATABRICKS_SECRETS.md) — creating the `quest-aws` scope and S3 credentials.
- The workflow appears in the Databricks UI as a job; run it from the UI or via CLI/API.

### Databricks Secrets (for S3)

- Create a secret scope (e.g. `quest-aws`) and store `access-key-id` and `secret-access-key` for S3 access. The ETL scripts (e.g. `datausa_population_sync.py`) use `dbutils.secrets.get("quest-aws", "access-key-id")` when running on Databricks; locally they fall back to default boto3 credentials. Step-by-step: [Databricks secrets](docs/DATABRICKS_SECRETS.md).

---

## Scaling and Next Steps

- **Config:** Move constants (buckets, prefixes, catalog/schema names) into a config file or module for easier env-specific settings.
- **Common functions:** Extract shared logic (e.g. S3 upload, table names, cleaning patterns) into a common module to reduce duplication.
- **Data quality:** Add DLT expectations or spark-expectations in the pipeline.
- **Cluster and compute (data-volume–driven):** As data volume grows, tune cluster configuration: choose the right cluster size, number of nodes and executors, enable **autoscaling** and **auto-termination** so cost and performance scale with workload.
- **Liquid clustering:** Enable **liquid clustering** with appropriate clustering keys on Delta tables; consider **auto liquid clustering** to keep layout optimized as data changes.
- **Incremental and upserts:** Enable **Delta Change Data Feed (CDF)** and use **Delta merge** for incremental loads and upserts instead of full overwrites, improving efficiency and supporting history/audit use cases.
---

## References

- [BrickFlow — Nike Engineering](https://engineering.nike.com/brickflow/v1.3.1/)
- [BrickFlow local deploy](docs/BRICKFLOW_LOCAL_DEPLOY.md) — deploying and validating the workflow locally.
- [Databricks secrets](docs/DATABRICKS_SECRETS.md) — S3 credentials via Databricks Secrets.
- Cursor and AI agents were used for syntax checks and to validate understanding of quest requirements
---

## Summary

| Step | What was done |
|------|----------------|
| 1–2 | Republish BLS and DataUSA data to S3; copy into Databricks as bronze (managed tables). |
| 3   | Silver layer (cleansing); Gold layer (Spark SQL views for analysis). Validation via notebooks. |
| 4   | Single BrickFlow workflow: S3 republish → bronze → silver → gold, with retries and email alerts. |

S3 is the source of truth; Databricks holds bronze/silver/gold in a medallion layout; BrickFlow keeps the pipeline in code with clear task and workflow dependencies.
