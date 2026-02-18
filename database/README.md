# Database

This folder contains AlloyDB schema definitions and seeding scripts.

## Contents

- `seed_data.sql` - Database schema with vector extension and ScaNN configuration
- `seed.py` - Python script to populate inventory with sample data
- `requirements.txt` - Python dependencies (psycopg2-binary, pgvector)

## Schema

The `inventory` table stores parts with vector embeddings for semantic search:

```sql
CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    part_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    description TEXT,
    stock_level INT DEFAULT 0,
    part_embedding vector(768)  -- text-embedding-005 dimension
);

-- ScaNN index for fast vector search
CREATE INDEX idx_inventory_scann
ON inventory USING scann (part_embedding cosine)
WITH (num_leaves=5, quantizer='sq8');
```

## ScaNN Index

**ScaNN (Scalable Nearest Neighbors)** uses vector quantization for:
- **10x faster** filtered search
- **4x faster** standard search
- **3x smaller** memory footprint

The `<=>` operator performs cosine distance (not similarity):

```sql
SELECT part_name, supplier_name
FROM inventory
ORDER BY part_embedding <=> query_vector
LIMIT 1;
```

> **Note:** When using parameterized queries with `%s` placeholders, you must cast: `%s::vector`. Example: `part_embedding <=> %s::vector`

## Sample Data

The seed script inserts 8 sample parts:
- Industrial Widget X-9 (Acme Corp)
- Precision Bolt M4 (Global Fasteners Inc)
- Hexagonal Nut M6 (Metro Supply Co)
- Phillips Head Screw 3x20 (Acme Corp)
- Wooden Dowel 10mm (Craft Materials Ltd)
- Rubber Gasket Small (SealTech Industries)
- Spring Tension 5kg (Mechanical Parts Co)
- Bearing 6204 (Bearings Direct)

Each part has a randomly generated 768-dimensional embedding vector for demo purposes.

## Running the Seed Script

### Automatic (via setup.sh)

The master setup script handles everything:
```bash
cd ../..
sh setup.sh
```

### Manual

```bash
# Ensure Auth Proxy is running
# Ensure DB_PASS is set

pip install -r requirements.txt
python3 seed.py
```

## Getting Database Credentials

Your database password comes from **Abi's AlloyDB setup tool**:

1. During infrastructure setup (Step 2 of setup.sh)
2. You enter a password in the Flask UI
3. **Save this password!**
4. Export it: `export DB_PASS='your-password'`

## Connection Details

The seed script connects via the AlloyDB Auth Proxy:

```python
psycopg2.connect(
    host="127.0.0.1",  # Auth Proxy tunnels to AlloyDB
    port=5432,
    user="postgres",
    password=os.environ["DB_PASS"],
    dbname="postgres",
)
```

## Vector Embeddings

Embeddings are generated using Google Gen AI SDK:

```python
from google import genai
from google.genai.types import EmbedContentConfig

client = genai.Client(vertexai=True, project="your-project", location="us-central1")
response = client.models.embed_content(
    model="text-embedding-005",
    contents=["Industrial Widget X-9"],
    config=EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768)
)
vector = response.embeddings[0].values  # 768-dimensional float array
```

## Troubleshooting

### DB_PASS not set

```bash
export DB_PASS='your-password-from-setup-ui'
```

### Auth Proxy not running

```bash
ps aux | grep alloydb-auth-proxy
```

If not running, start it via `sh run.sh` or manually.

### Connection refused

Ensure AlloyDB instance exists:
```bash
gcloud alloydb instances list --region=us-central1
```

### Seed script fails

Check Auth Proxy logs:
```bash
cat ../proxy.log
```

Common issues:
- Wrong password
- Auth Proxy not connected
- AlloyDB instance not ready (wait 1-2 minutes after provisioning)

## Production Considerations

For production deployments:

1. **Use real embeddings**: Generate embeddings from actual part descriptions
2. **Tune ScaNN**: Adjust `num_leaves` based on dataset size (typically sqrt of row count)
3. **Add indexes**: Create indexes on frequently queried columns
4. **Enable replication**: Use AlloyDB read replicas for high availability
5. **Monitor performance**: Use Cloud Monitoring for query latency metrics

## Learn More

- [AlloyDB AI Documentation](https://cloud.google.com/alloydb/docs/ai)
- [ScaNN Overview](https://cloud.google.com/alloydb/docs/ai/work-with-embeddings)
- [pgvector Extension](https://github.com/pgvector/pgvector)
