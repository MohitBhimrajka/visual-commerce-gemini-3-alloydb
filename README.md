# Autonomous Supply Chain with Gemini 3 Flash & AlloyDB AI

Build an **agentic supply chain system** that "sees" physical inventory using Gemini 3 Flash (Code Execution), "remembers" millions of parts using AlloyDB AI (ScaNN), and "transacts" using the A2A Protocol.

## What You'll Build

A multi-agent system featuring:
- **Vision Agent**: Uses Gemini 3 Flash to count inventory items deterministically via code execution
- **Supplier Agent**: Searches millions of parts using AlloyDB ScaNN vector search
- **Control Tower**: Real-time WebSocket UI for orchestrating autonomous workflows

## Architecture

![Autonomous Supply Chain Architecture](./assets/architecture-diagram.png)

**Key Components:**
- **Control Tower (port 8080):** WebSocket-based UI for real-time orchestration and agent coordination
- **Vision Agent (port 8081):** Gemini 3 Flash with Code Execution for deterministic vision (API key)
- **Supplier Agent (port 8082):** AlloyDB ScaNN vector search for semantic part matching (GCP credentials)
- **AlloyDB AI:** Enterprise PostgreSQL with ScaNN index for fast nearest-neighbor search
- **A2A Protocol:** Dynamic agent discovery via `/.well-known/agent-card.json`

**Hybrid Architecture:** Vision Agent uses Gemini API (simple setup, free tier available), while Supplier Agent uses GCP services (enterprise-grade, compliance-ready).

## Quick Start

### Prerequisites

- Google Cloud Project with billing enabled
- Cloud Shell or local environment with:
  - `gcloud` CLI configured
  - Python 3.9+
  - Git

### Setup & Run

```bash
# 1. Clone the repository
git clone https://github.com/MohitBhimrajka/visual-commerce-gemini-3-alloydb.git
cd visual-commerce-gemini-3-alloydb

# 2. Run setup (provisions infrastructure + seeds database)
./setup.sh

# 3. Start all services
./run.sh
```

> **📌 Note:** All commands assume you're in the repo root (`visual-commerce-gemini-3-alloydb/`). If commands fail with "No such file", verify your location with `pwd` and navigate back to the repo.

Open http://localhost:8080 to see the Control Tower.

## Repository Structure

```
visual-commerce-gemini-3-alloydb/
├── README.md                    # You are here
├── setup.sh                     # One-click setup script
├── run.sh                       # One-click run script
├── .env.example                 # Environment variables template
│
├── agents/                      # Agentic components
│   ├── vision-agent/            # Gemini 3 Flash vision analysis
│   └── supplier-agent/          # AlloyDB ScaNN inventory search
│
├── frontend/                    # FastAPI + WebSocket Control Tower
│   ├── app.py                   # Main server
│   └── static/                  # Real-time UI
│
├── database/                    # AlloyDB schema & seeding
│   ├── seed.py                  # Database initialization
│   └── seed_data.sql            # Schema definition
│
├── test-images/                 # Sample warehouse images for testing
│
└── logs/                        # Runtime logs (gitignored)
    ├── proxy.log
    ├── vision-agent.log
    ├── supplier-agent.log
    └── frontend.log
```

## What Each Command Does

### `./setup.sh`

1. **Validates environment** - Checks gcloud, APIs, project settings
2. **Clones infrastructure tool** - Gets AlloyDB setup tool
3. **Launches setup UI** - Guides you through AlloyDB provisioning (~15 min)
4. **Enables Public IP** - If on Cloud Shell, offers to enable Public IP (secure: mTLS + IAM + password complexity)
5. **Seeds database** - Populates inventory with sample data and creates ScaNN index

### `./run.sh`

1. **Starts AlloyDB Auth Proxy** - Creates secure tunnel to database (uses `--public-ip` if available)
2. **Launches Vision Agent** - Port 8081 (Gemini 3 Flash)
3. **Launches Supplier Agent** - Port 8082 (AlloyDB ScaNN)
4. **Starts Control Tower** - Port 8080 (FastAPI + WebSocket UI)

## Key Technologies

- **Gemini 3 Flash** - AI model with code execution for deterministic vision
- **AlloyDB AI** - PostgreSQL-compatible database with ScaNN vector search
- **A2A Protocol** - Agent-to-Agent communication standard
- **FastAPI** - Modern Python web framework with WebSocket support

## Troubleshooting

### Port conflicts

```bash
lsof -ti:8080 | xargs kill -9
lsof -ti:8081 | xargs kill -9
lsof -ti:8082 | xargs kill -9
```

### AlloyDB connection issues

```bash
# 1. Check if Auth Proxy is running
ps aux | grep alloydb-auth-proxy

# 2. Check proxy logs
tail -50 logs/proxy.log
```

**Common causes:**

1. **Wrong password** - Check `.env`: `cat .env | grep DB_PASS`
2. **Proxy not running** - Restart with `./run.sh`
3. **Port 5432 in use** - Kill existing process: `lsof -ti:5432 | xargs kill -9`

> **Why do I need the Auth Proxy?** AlloyDB's private IP (172.21.0.x) is only reachable from inside the VPC. Cloud Shell runs outside the VPC. The Auth Proxy creates a secure mTLS tunnel from `127.0.0.1:5432` to your AlloyDB instance. If Public IP is enabled, the proxy connects via the public endpoint.

### Agent not responding

```bash
curl http://localhost:8081/health
curl http://localhost:8082/health
curl http://localhost:8080/api/health
```

## Cleanup

To avoid charges, delete the AlloyDB cluster:

```bash
# Replace with your cluster name (check .env for ALLOYDB_CLUSTER)
gcloud alloydb clusters delete YOUR_CLUSTER_NAME \
  --region=us-central1 \
  --force
```

## Technical References

### **Official Documentation & Performance Benchmarks**

**Gemini 3 Flash:**
- Code Execution API: https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/code-execution-api
- Developer Guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Model Documentation: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash
- Pricing: https://ai.google.dev/gemini-api/docs/pricing

**AlloyDB ScaNN Performance (All claims verified from official sources):**
- ScaNN vs HNSW Benchmarks: https://cloud.google.com/blog/products/databases/how-scann-for-alloydb-vector-search-compares-to-pgvector-hnsw
  - ✅ 10x faster filtered search (when indices exceed memory)
  - ✅ 4x faster standard search
  - ✅ 3-4x smaller memory footprint
  - ✅ 8x faster index builds
- Understanding ScaNN: https://cloud.google.com/blog/products/databases/understanding-the-scann-index-in-alloydb
- AlloyDB AI Documentation: https://cloud.google.com/alloydb/docs/ai
- Best Practices: https://docs.cloud.google.com/alloydb/docs/ai/best-practices-tuning-scann

**A2A Protocol:**
- Agent cards at `/.well-known/agent-card.json` (emerging standard)
- Standardized agent discovery and communication

**Additional Context:**
- ScaNN is based on 12 years of Google Research and powers Google Search and YouTube at billion-scale
- Released for general availability: October 2024
- First PostgreSQL vector index suitable for million-to-billion vectors