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

## Set Your Project

Confirm your GCP project is set:

```bash
gcloud config set project <YOUR_PROJECT_ID>
```

## Run Setup Script

In the Cloud Shell terminal at the bottom of your screen, run:

```bash
sh setup.sh
```

> **Note:** If the script reports "Not authenticated with gcloud", run `gcloud auth login` first, then re-run `sh setup.sh`

**What happens:**

- Validates your environment (gcloud, Python, project settings)
- Prompts you for your Gemini API key (paste the key from previous step)
- Checks and enables required APIs
- Auto-detects your AlloyDB instance and extracts region, cluster, and instance name
- Asks for your database password
- Creates the `.env` configuration file
- Installs Python dependencies

**If you need to restart:**
- You can safely re-run `sh setup.sh` — it loads existing `.env` values

## Enable Public IP on AlloyDB

Enable Public IP so the Python Connector can connect from Cloud Shell:

1. Go to [AlloyDB Console](https://console.cloud.google.com/alloydb/clusters)
2. Click your instance → **Edit** → Enable **Public IP** → **Update**

> **💡 Note:** The AlloyDB Python Connector handles authentication and encryption — you don't need to add any authorized external networks.

## Grant Vertex AI Permissions

```bash
PROJECT_ID=$(gcloud config get-value project)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:service-$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")@gcp-sa-alloydb.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## Set Up the Database

Connect to **AlloyDB Studio** (in the AlloyDB Console → your instance → AlloyDB Studio). Sign in with username `postgres` and your password.

Run these SQL blocks **one at a time** in AlloyDB Studio:

**1. Enable extensions:**
```sql
CREATE EXTENSION IF NOT EXISTS google_ml_integration CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS alloydb_scann CASCADE;
```

**2. Create the inventory table:**
```sql
DROP TABLE IF EXISTS inventory;
CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    part_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    description TEXT,
    stock_level INT DEFAULT 0,
    part_embedding vector(768)
);
```

**3. Insert sample data (20 items):**
```sql
INSERT INTO inventory (part_name, supplier_name, description, stock_level) VALUES
('Cardboard Shipping Box Large', 'Packaging Solutions Inc', 'Heavy-duty corrugated cardboard shipping container, 24x18x12 inches', 250),
('Warehouse Storage Container', 'Industrial Supply Co', 'Stackable plastic storage bin with snap-lock lid, blue', 180),
('Product Shipping Boxes', 'Acme Packaging', 'Medium corrugated boxes for warehouse storage, 18x14x10 inches', 320),
('Industrial Widget X-9', 'Acme Corp', 'Heavy-duty industrial coupling for pneumatic systems', 50),
('Precision Bolt M4', 'Global Fasteners Inc', 'Stainless steel M4 allen bolt, 20mm length, grade A2-70', 200),
('Hexagonal Nut M6', 'Metro Supply Co', 'Galvanized steel hex nut M6, DIN 934 standard', 150),
('Phillips Head Screw 3x20', 'Acme Corp', 'Zinc-plated Phillips head wood screw, 3mm x 20mm', 500),
('Wooden Dowel 10mm', 'Craft Materials Ltd', 'Hardwood birch dowel rod, 10mm diameter x 300mm length', 80),
('Rubber Gasket Small', 'SealTech Industries', 'Buna-N rubber gasket, 25mm OD x 15mm ID, oil resistant', 120),
('Spring Tension 5kg', 'Mechanical Parts Co', 'Stainless steel compression spring, 5kg load capacity', 60),
('Bearing 6204', 'Bearings Direct', 'Deep groove ball bearing 6204-2RS, 20x47x14mm sealed', 45),
('Warehouse Shelf Boxes', 'Storage Systems Ltd', 'Standardized warehouse inventory boxes, corrugated, bulk pack', 400),
('Inventory Container Units', 'Supply Chain Pros', 'Modular stackable storage units for warehouse racking', 95),
('Aluminum Extrusion Bar', 'MetalWorks International', 'T-slot aluminum extrusion 20x20mm profile, 1 meter length', 110),
('Cable Tie Pack 200mm', 'ElectroParts Depot', 'Nylon cable ties, 200mm x 4.8mm, UV resistant black, pack of 100', 600),
('Hydraulic Hose 1/2 inch', 'FluidPower Systems', 'High-pressure hydraulic hose, 1/2 inch ID, 3000 PSI rated', 35),
('Safety Goggles Clear', 'WorkSafe Equipment Co', 'ANSI Z87.1 rated clear safety goggles, anti-fog coating', 275),
('Packing Tape Industrial', 'Packaging Solutions Inc', 'Heavy-duty polypropylene packing tape, 48mm x 100m, clear', 450),
('Stainless Steel Sheet 1mm', 'MetalWorks International', '304 stainless steel sheet, 1mm thickness, 300x300mm', 70),
('Silicone Sealant Tube', 'SealTech Industries', 'Industrial-grade RTV silicone sealant, 300ml cartridge, grey', 190);
```

**4. Grant permission and generate embeddings:**
```sql
GRANT EXECUTE ON FUNCTION embedding TO postgres;

UPDATE inventory
SET part_embedding = ai.embedding('text-embedding-005', part_name || '. ' || description)::vector
WHERE part_embedding IS NULL;
```

**5. Create the ScaNN index:**
```sql
SET scann.allow_blocked_operations = true;
CREATE INDEX IF NOT EXISTS idx_inventory_scann
ON inventory USING scann (part_embedding cosine)
WITH (num_leaves=5, quantizer='sq8');
```

**6. Verify — you should see 20 rows with embeddings:**
```sql
SELECT part_name, supplier_name, (part_embedding IS NOT NULL) as has_embedding FROM inventory ORDER BY id;
```

## Enable Memory (Code Change 1)

Time to awaken the agent's memory! The Supplier Agent needs to search parts using **vector similarity**.

**Open the file:** `agents/supplier-agent/inventory.py`

**Find the TODO** in the `find_supplier()` function (around line 70-80) and replace the placeholder:

```python
sql = """
SELECT part_name, supplier_name,
       part_embedding <=> %s::vector as distance
FROM inventory
ORDER BY part_embedding <=> %s::vector
LIMIT 1;
"""
cursor.execute(sql, (embedding_str, embedding_str))
```

**Save the file** (Ctrl+S or Cmd+S)

The `<=>` operator performs cosine distance calculation using AlloyDB's ScaNN index. Note: we use `embedding_str` (the string-formatted vector) because pg8000 requires it.

## Enable Vision (Code Change 2)

Now let's awaken the agent's eyes! The Vision Agent uses Gemini 3 Flash with **Code Execution**.

**Open the file:** `agents/vision-agent/agent.py`

**Find the `GenerateContentConfig` section** (around line 68-78). **Uncomment** both:

1. The `thinking_config` block
2. The `tools` block

**Save the file**

Code Execution allows Gemini to write Python to count items deterministically instead of guessing.

## Review the Agent Card

The A2A Protocol uses **agent cards** for discovery. The card is already included at `agents/supplier-agent/agent_card.json`.

Open it to review — feel free to customize the name, description, or examples.

## Start All Services

Time to bring everything online!

```bash
sh run.sh
```

Wait ~10 seconds, then open **Web Preview** (👁️) → **Preview on port 8080**.

## Test the Autonomous Workflow

1. **Upload an image** or click a sample image
2. **Watch the magic:**
   - Vision Agent writes Python code to count items
   - Supplier Agent finds the nearest part match via ScaNN
   - System places an autonomous order
3. Toggle **DEMO mode** to pause at each stage

## 🎁 Bonus: Deploy to Cloud Run

> **Optional** — Everything works locally! But if you'd like to share your creation:

```bash
sh deploy/deploy.sh
```

The script reads your `.env`, asks for your name, and deploys to Cloud Run. When anyone opens your URL, they'll see a popup saying:

> 🚀 **Deployed by *Your Name*** — Powered by Gemini 3 Flash · AlloyDB AI · A2A Protocol
> *Completed as part of Code Vipassana Season 14*
> **[Try the codelab yourself →]**

After they dismiss it, a small persistent badge stays at the bottom: *"Deployed by Your Name · Code Vipassana S14 · Learn how →"*

> **Completed as part of [Code Vipassana Season 14](https://www.codevipassana.dev/)**

## What Just Happened?

Congratulations! You've built an **agentic AI system** that:

✅ **Sees deterministically** — Gemini 3 Flash Code Execution (no hallucinations)
✅ **Remembers semantically** — AlloyDB ScaNN vector search in milliseconds
✅ **Acts autonomously** — A2A Protocol for dynamic agent discovery
✅ **Operates in real-time** — WebSocket streaming

🎉 **Your autonomous supply chain is now operational!**
