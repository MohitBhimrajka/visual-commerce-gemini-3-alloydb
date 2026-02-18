# Agents

This folder contains the autonomous agents that power the supply chain system.

## Architecture

The agents communicate using the **A2A (Agent-to-Agent) Protocol**, exposing standardized endpoints for discovery and interaction.

```
agents/
├── vision-agent/       Port 8081 - Gemini 3 Flash for deterministic vision
└── supplier-agent/     Port 8082 - AlloyDB ScaNN for inventory search
```

## Agent Communication

All agents expose:
- `/.well-known/agent-card.json` - Agent card for discovery (A2A standard path)
- `/health` - Health check endpoint
- WebSocket/HTTP endpoints for message passing

## Vision Agent

**Purpose**: Analyze images and count inventory items deterministically

**Technology**: Gemini 3 Flash with Code Execution

**How it works**:
1. Receives image via A2A protocol
2. Gemini thinks: "I need to count items"
3. Gemini acts: Writes Python code (OpenCV) to count
4. Gemini observes: Executes code and verifies result
5. Returns exact count (not a guess!)

**Port**: 8081

## Supplier Agent

**Purpose**: Find matching suppliers from millions of inventory records

**Technology**: AlloyDB AI with ScaNN vector search

**How it works**:
1. Receives part description via A2A protocol
2. Generates embedding using Vertex AI text-embedding-005
3. Queries AlloyDB using ScaNN `<=>` operator (cosine distance)
4. Returns best match with supplier and confidence score

**Port**: 8082

## Running the Agents

### Quick Start

Use the master run script:
```bash
cd ../..
sh run.sh
```

### Manual Start

```bash
# Start Vision Agent
cd vision-agent
pip install -r requirements.txt
uvicorn main:asgi_app --host 0.0.0.0 --port 8081

# Start Supplier Agent
cd ../supplier-agent
pip install -r requirements.txt
uvicorn main:asgi_app --host 0.0.0.0 --port 8082
```

## A2A Protocol

Each agent exposes an agent card describing its capabilities:

```json
{
  "name": "Vision Inspection Agent",
  "description": "Autonomous computer vision agent...",
  "skills": [
    {
      "id": "audit_inventory",
      "name": "Audit Inventory via Image",
      "description": "Analyzes an image to count items..."
    }
  ]
}
```

The Control Tower discovers agents dynamically by fetching their cards.

## Environment Variables

### Vision Agent

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
```

### Supplier Agent

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export DB_PASS=your-database-password
```

## Troubleshooting

### Port already in use

```bash
lsof -ti:8081 | xargs kill -9
lsof -ti:8082 | xargs kill -9
```

### Agent not responding

Check health endpoints:
```bash
curl http://localhost:8081/health
curl http://localhost:8082/health
```

### Database connection issues (Supplier Agent)

Ensure:
1. AlloyDB Auth Proxy is running
2. DB_PASS environment variable is set
3. Database was seeded successfully

## Learn More

- [A2A Protocol Documentation](https://a2aproject.github.io)
- [Gemini Code Execution](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/code-execution)
- [AlloyDB AI ScaNN](https://cloud.google.com/alloydb/docs/ai/work-with-embeddings)
