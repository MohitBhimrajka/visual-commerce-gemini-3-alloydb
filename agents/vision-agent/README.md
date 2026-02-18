# Vision Agent

Autonomous computer vision agent using **Gemini 3 Flash** with code execution for deterministic inventory counting.

## The Problem

Standard multimodal models *predict* item counts based on pixel patterns. In a supply chain, predictions are dangerous:
- Model says: "Approximately 12 boxes"
- Reality: 15 boxes
- Result: Stockout, emergency shipping, $50K cost

## The Solution: Deterministic Vision

Instead of predicting, this agent:
1. **Thinks**: "I need to count items precisely"
2. **Acts**: Writes Python code (OpenCV) to detect and count
3. **Observes**: Executes code and verifies result
4. **Returns**: Exact count (not a guess!)

## Technology

- **Gemini 3 Flash** (`gemini-3-flash-preview`) with:
  - `thinking_level="LOW"` - Fast reasoning
  - `ToolCodeExecution` - Sandboxed Python execution
- **Vertex AI SDK** - `google-genai` package
- **A2A Protocol** - Agent discovery and communication

## Files

- `agent.py` - Core Gemini logic
- `agent_executor.py` - A2A protocol bridge
- `main.py` - FastAPI server (port 8081)
- `requirements.txt` - Python dependencies
- `assets/warehouse_shelf.png` - Sample warehouse image for standalone verification

## Code Execution Flow

```python
# 1. Configure Gemini with code execution
config = types.GenerateContentConfig(
    temperature=0,
    thinking_level="LOW",
    tools=[types.Tool(code_execution=types.ToolCodeExecution())]
)

# 2. Send image + prompt
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[image_part, "Write code to count boxes"],
    config=config
)

# 3. Extract results
for part in response.candidates[0].content.parts:
    if hasattr(part, 'executable_code'):
        code = part.executable_code.code  # Python code
    if hasattr(part, 'code_execution_result'):
        output = part.code_execution_result.output  # Execution result
```

## Running

### Via Master Script

```bash
cd ../..
sh run.sh
```

### Manually

```bash
pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
uvicorn main:asgi_app --host 0.0.0.0 --port 8081
```

### Standalone Testing

```bash
python3 agent.py
```

This runs analysis on `assets/warehouse_shelf.png`.

## A2A Agent Card

Exposed at `http://localhost:8081/.well-known/agent-card.json`:

```json
{
  "name": "Vision Inspection Agent",
  "description": "Autonomous computer vision agent...",
  "version": "1.0.0",
  "skills": [{
    "id": "audit_inventory",
    "name": "Audit Inventory via Image",
    "description": "Analyzes image to count items using Gemini 3 Flash code execution"
  }]
}
```

## Request Format

Send via A2A protocol:

```json
{
  "image_base64": "<base64-encoded-image>",
  "query": "Write code to count the exact number of boxes on this shelf."
}
```

## Response Format

```json
{
  "answer": "I counted 15 boxes...",
  "code_output": "Count: 15\nDetection complete.",
  "plan": "Generated code: import cv2..."
}
```

## Environment Variables

```bash
# Required
export GOOGLE_CLOUD_PROJECT=your-project-id

# Optional
export VISION_AGENT_URL=http://localhost:8081
```

## Customization

### Adjust Thinking Level

For faster (but less thorough) analysis:

```python
thinking_level="LOW"
```

Cost tradeoff:
- `HIGH`: Most accurate, slowest, most expensive
- `MEDIUM`: Balanced
- `LOW`: Fastest (used in this codelab)

### Change Model

```python
model="gemini-3-flash-preview"  # Latest
model="gemini-1.5-flash"         # Stable alternative
```

### Custom Prompts

Modify query in `agent_executor.py`:

```python
query = "Count items and identify their types"  # More detailed
query = "Detect defects in the image"           # Quality control
query = "Measure dimensions of objects"         # Inspection
```

## Troubleshooting

### Vertex AI permission denied

```bash
gcloud services enable aiplatform.googleapis.com
```

### Model not found

Ensure you're using the correct model name:
```python
model="gemini-3-flash-preview"  # ← Correct
```

### Code execution disabled

Check that tools are properly configured:
```python
tools=[types.Tool(code_execution=types.ToolCodeExecution())]
```

### Empty response

Verify:
1. Image is valid (< 10MB, supported format)
2. GOOGLE_CLOUD_PROJECT is set
3. Model quota not exceeded

## Learn More

- [Gemini Code Execution Docs](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/code-execution)
- [Vertex AI SDK](https://cloud.google.com/vertex-ai/docs/python-sdk/use-vertex-ai-python-sdk)
- [A2A Protocol](https://a2aproject.github.io)
