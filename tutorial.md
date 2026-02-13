# Autonomous Supply Chain with Gemini 3 Flash & AlloyDB AI

## Welcome! Click to start

You'll build an **agentic supply chain system** that uses Gemini 3 Flash for deterministic vision (code execution), AlloyDB AI for semantic search (ScaNN vector index), and the A2A Protocol for autonomous agent coordination.

## Get Your Gemini API Key

The Vision Agent needs a Gemini API key to access Gemini 3 Flash with Code Execution.

**Steps:**

1. Open [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) in a new browser tab
2. Click **"Create API Key"**
3. Copy the API key to your clipboard
4. Keep the tab open - you'll paste this key in the next step

## Run Setup Script

In the Cloud Shell terminal at the bottom of your screen, run:

```bash
./setup.sh
```

**What happens:**

- Validates your environment (gcloud, Python, project settings)
- Prompts you for your Gemini API key (paste the key from previous step)
- Clones the AlloyDB setup tool
- Launches the infrastructure provisioning UI on port 8080
- This takes **~15-20 minutes total** (perfect time for a coffee break ☕)

When prompted for your API key, paste it and press Enter.

## Access the Setup UI

Once you see the message **"Starting infrastructure setup UI..."**:

1. Click the **Web Preview** button (eye icon 👁️) in the Cloud Shell toolbar
2. Select **"Preview on port 8080"**
3. The AlloyDB provisioning UI will open in a new tab

## Configure & Deploy Infrastructure

In the provisioning UI, you'll see a form:

**Fill in these fields:**

1. **Project ID:** Should be auto-filled with your current project
2. **Region:** Select `us-central1` (or your preferred region)
3. **Database Password:** 
   - Create a **strong password**
   - **SAVE THIS PASSWORD** - you'll need it in the next step
   - This is the ONLY credential you need to remember

**Click "Start Deployment"**

The deployment creates:
- VPC network with subnets
- Private Service Access
- AlloyDB Cluster
- AlloyDB Primary Instance

**This takes approximately 15 minutes.** You'll see progress updates in the UI.

## Complete Setup & Seed Database

Once the deployment finishes, you'll see the connection details displayed in the UI.

**Now, back in your Cloud Shell terminal:**

1. Press **Ctrl+C** to stop the UI server
2. The setup script will automatically:
   - **Auto-detect** your AlloyDB instance (cluster, region, project)
   - Prompt you for the database password
3. **When prompted for password:** Enter the password you saved in the previous step
4. The script will then:
   - Set up the AlloyDB Auth Proxy (with secure mTLS connection)
   - Seed the database with 8 sample inventory parts
   - Create the ScaNN vector index for fast semantic search

**Wait for the message:** `✅ Database seeded successfully!`

## Enable Memory (Code Change 1)

Time to awaken the agent's memory! The Supplier Agent needs to search millions of parts using **vector similarity**.

**Open the file:** `agents/supplier-agent/inventory.py`

**Find line ~45** with the `TODO` comment and the placeholder query.

**Replace the TODO section** with this ScaNN vector query:

```python
sql = """
SELECT part_name, supplier_name,
       part_embedding <=> %s::vector as distance
FROM inventory
ORDER BY part_embedding <=> %s::vector
LIMIT 1;
"""
cursor.execute(sql, (embedding_vector, embedding_vector))
return cursor.fetchone()
```

**Save the file** (Ctrl+S or Cmd+S)

**What this does:** The `<=>` operator performs cosine distance calculation using AlloyDB's ScaNN index, enabling lightning-fast semantic search across millions of vectors.

## Enable Vision (Code Change 2)

Now let's awaken the agent's eyes! The Vision Agent uses Gemini 3 Flash with **Code Execution** for deterministic counting.

**Open the file:** `agents/vision-agent/agent.py`

**Find the `GenerateContentConfig` section** (around line 35-45).

You'll see two commented blocks. **Uncomment both:**

1. The `thinking_config` block:
```python
thinking_config=types.ThinkingConfig(
    thinking_level=types.ThinkingLevel.HIGH  # Use MEDIUM in production
),
```

2. The `tools` block:
```python
tools=[types.Tool(code_execution=types.ToolCodeExecution())]
```

**Save the file** (Ctrl+S or Cmd+S)

**What this does:** Code Execution allows Gemini to write Python (OpenCV) to count items deterministically instead of guessing. ThinkingConfig enables deep reasoning before acting.

## Create the Agent Card

The A2A Protocol uses **agent cards** for discovery. Each agent exposes its capabilities via `/.well-known/agent-card.json`.

**First, copy the skeleton:**

```bash
cp agents/supplier-agent/agent_card_skeleton.json agents/supplier-agent/agent_card.json
```

**Now open:** `agents/supplier-agent/agent_card.json`

**Replace the entire contents** with:

```json
{
  "name": "Acme Supplier Agent",
  "description": "Autonomous fulfillment for industrial parts via AlloyDB ScaNN.",
  "version": "1.0.0",
  "skills": [{
    "id": "search_inventory",
    "name": "Search Inventory",
    "description": "Searches warehouse database using AlloyDB ScaNN vector search.",
    "tags": ["inventory", "search", "alloydb"],
    "examples": ["Find stock for Industrial Widget X-9", "Who supplies ball bearings?"]
  }]
}
```

**Save the file**

**What this does:** The Control Tower will discover this agent automatically by reading its card. No hardcoded endpoints or SDKs needed!

## Start All Services

Time to bring everything online! Run the master start script:

```bash
./run.sh
```

**This starts 4 services:**

- **AlloyDB Auth Proxy** (port 5432) - Secure database connection
- **Vision Agent** (port 8081) - Gemini 3 Flash with Code Execution
- **Supplier Agent** (port 8082) - AlloyDB ScaNN vector search
- **Control Tower** (port 8080) - WebSocket orchestration UI

**Wait ~10 seconds** for all services to initialize. You'll see health check confirmations for each service.

## Access the Control Tower

The Control Tower is your real-time dashboard for the autonomous supply chain.

**To access it:**

1. Click the **Web Preview** button (👁️) in the Cloud Shell toolbar
2. Select **"Preview on port 8080"**
3. The Control Tower dashboard will open

**You'll see:**
- Three agent status cards (Vision, Supplier, Action)
- A progress timeline
- A chat log for real-time updates

## Test the Autonomous Workflow

Time to see the agents in action!

**Steps:**

1. **Upload an image:**
   - Click the upload area or drag & drop
   - Use a warehouse/shelf image (or sample images in `test-images/` folder)

2. **Click "Initiate Autonomous Workflow"**

3. **Watch the magic happen in real-time:**
   - **Discovery:** Frontend discovers agents via A2A protocol
   - **Vision Analysis:** Gemini 3 Flash writes Python code to count items deterministically
   - **Memory Search:** AlloyDB ScaNN finds the exact part match in milliseconds
   - **Autonomous Action:** System places order without human intervention

**You'll see:**
- Agent cards update with live status
- Code execution output displayed with syntax highlighting
- Vector search results with similarity scores
- Final order confirmation

## What Just Happened?

Congratulations! You've built an **agentic AI system** that:

✅ **Sees deterministically** - Gemini 3 Flash Code Execution writes OpenCV code to count pixels (no hallucinations)

✅ **Remembers semantically** - AlloyDB ScaNN performs vector search across millions of parts in milliseconds

✅ **Acts autonomously** - A2A Protocol enables dynamic agent discovery and coordination

✅ **Operates in real-time** - WebSocket streaming shows you every step of the autonomous loop

### The Hybrid Architecture

- **Vision Agent:** Uses Gemini API (API key) - simple, free tier available
- **Supplier Agent:** Uses GCP (Vertex AI + AlloyDB) - enterprise-grade, compliance-ready

This is **deterministic AI engineering** - building systems that don't guess. You've moved from "Generative AI" to "Agentic AI."

🎉 **Your autonomous supply chain is now operational!**
