# Supplier Agent

Autonomous inventory search agent using **AlloyDB AI** with ScaNN vector search for high-speed semantic matching.

## The Problem

Searching millions of parts by exact text match is:
- Brittle ("Widget X-9" vs "WidgetX9")
- Slow (full table scans)
- Language-dependent (English vs Spanish)

## The Solution: Semantic Vector Search

This agent uses embeddings + ScaNN:
1. Convert part description to 768-dimensional vector
2. Search for nearest vectors using cosine distance (`<=>` operator)
3. Return best match with supplier and confidence
4. Results in milliseconds, even with millions of parts

## Technology

- **AlloyDB AI** - PostgreSQL-compatible with AI extensions
- **ScaNN** (Scalable Nearest Neighbors) - Vector quantization for speed
- **Vertex AI Embeddings** - `text-embedding-005` model
- **pgvector** - PostgreSQL vector extension
- **A2A Protocol** - Agent discovery and communication

## Files

- `inventory.py` - AlloyDB ScaNN query logic
- `agent_executor.py` - A2A protocol bridge
- `main.py` - FastAPI server (port 8082)
- `agent_card_skeleton.json` - Template for agent card
- `requirements.txt` - Python dependencies

## ScaNN Query

The core search uses PostgreSQL's `<=>` cosine distance operator:

```python
sql = """
SELECT part_name, supplier_name,
       (part_embedding <=> %s::vector) as distance
FROM inventory
ORDER BY part_embedding <=> %s::vector
LIMIT 1;
"""
cursor.execute(sql, (embedding_vector, embedding_vector))
```

> **Critical:** The `::vector` cast is mandatory when using `%s` placeholders with vector operators. Without it, PostgreSQL throws: `operator does not exist: vector <=> double precision`

## Why ScaNN?

Standard vector search (HNSW) is memory-intensive. ScaNN uses vector quantization:

- **10x faster** filtered search
- **4x faster** standard search  
- **3x smaller** memory footprint

The index fits in CPU L2 cache for maximum speed.

## Running

### Via Master Script

```bash
cd ../..
./run.sh
```

### Manually

```bash
pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
export DB_PASS='your-password'
uvicorn main:asgi_app --host 0.0.0.0 --port 8082
```

## A2A Agent Card

Create from skeleton:

```bash
cp agent_card_skeleton.json agent_card.json
# Edit with your agent details
```

Exposed at `http://localhost:8082/.well-known/agent-card.json`:

```json
{
  "name": "Acme Supplier Agent",
  "description": "Autonomous fulfillment for industrial parts",
  "skills": [{
    "id": "search_inventory",
    "name": "Search Inventory",
    "description": "Find supplier using AlloyDB ScaNN vector search"
  }]
}
```

## Request Format

Send via A2A protocol:

```json
{
  "query": "Industrial Widget"
}
```

Or with pre-computed embedding:

```json
{
  "embedding": [0.1, 0.2, ..., 0.05]  // 768-dimensional vector
}
```

## Response Format

```json
{
  "part": "Industrial Widget X-9",
  "supplier": "Acme Corp",
  "match_confidence": "98.5%"
}
```

## Database Connection

Connects via AlloyDB Auth Proxy:

```python
psycopg2.connect(
    host="127.0.0.1",  # Auth Proxy tunnel
    port=5432,
    user="postgres",
    password=os.environ["DB_PASS"],
    dbname="postgres",
)
```

## Environment Variables

```bash
# Required
export GOOGLE_CLOUD_PROJECT=your-project-id
export DB_PASS=your-database-password

# Optional
export SUPPLIER_AGENT_URL=http://localhost:8082
```

## Embedding Generation

Uses Vertex AI to convert text to vectors:

```python
from vertexai.language_models import TextEmbeddingModel

model = TextEmbeddingModel.from_pretrained("text-embedding-005")
embeddings = model.get_embeddings(["Industrial Widget"])
vector = embeddings[0].values  # 768 dimensions
```

## ScaNN Index Configuration

Created during database seeding:

```sql
CREATE INDEX idx_inventory_scann
ON inventory USING scann (part_embedding cosine)
WITH (
    num_leaves=5,      -- Adjust based on dataset size (sqrt of row count)
    quantizer='sq8'    -- 8-bit scalar quantization
);
```

## Customization

### Tune for Dataset Size

For production with millions of parts:

```sql
WITH (
    num_leaves=1000,           -- sqrt(1M) ≈ 1000
    quantizer='sq8',
    num_leaves_to_search=10    -- Search top 10 leaves
);
```

### Change Distance Metric

```sql
USING scann (part_embedding l2)  -- L2 distance instead of cosine
```

### Return Top N Results

```sql
LIMIT 5  -- Return top 5 matches instead of 1
```

### Add Filtering

```sql
WHERE stock_level > 0  -- Only in-stock items
ORDER BY part_embedding <=> %s::vector
```

## Troubleshooting

### Connection refused

Ensure Auth Proxy is running:
```bash
ps aux | grep alloydb-auth-proxy
```

### Authentication failed

Check DB_PASS:
```bash
echo $DB_PASS  # Should match password from setup
```

### No results returned

Verify data was seeded:
```sql
SELECT COUNT(*) FROM inventory;
```

Should return 8 (or more).

### Slow queries

Check index exists:
```sql
\di  -- List indexes
```

Should see `idx_inventory_scann`.

## Performance

Typical query latency:
- **< 5ms** for 10K parts
- **< 50ms** for 1M parts
- **< 500ms** for 100M parts (with tuned index)

## Learn More

- [AlloyDB AI Documentation](https://cloud.google.com/alloydb/docs/ai)
- [ScaNN Overview](https://cloud.google.com/alloydb/docs/ai/work-with-embeddings)
- [Vertex AI Embeddings](https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings)
- [pgvector Extension](https://github.com/pgvector/pgvector)
