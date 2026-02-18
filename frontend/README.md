# Control Tower Frontend

The **Control Tower** is a real-time web interface for orchestrating autonomous supply chain workflows.

## Technology Stack

- **FastAPI** - Modern Python web framework
- **WebSockets** - Real-time bidirectional communication
- **Tailwind CSS** - Utility-first styling
- **Alpine.js** - Lightweight reactive JavaScript
- **Highlight.js** - Syntax highlighting for code execution results

## Architecture

```
Browser                FastAPI Server              Agents
   │                         │                       │
   │─────Upload Image───────>│                       │
   │                         │                       │
   │<────WebSocket Open──────│                       │
   │                         │                       │
   │                         │────A2A Request───────>│
   │                         │                       │
   │<───Event: discovery─────│<──────Response───────│
   │<───Event: vision_start──│                       │
   │<───Event: vision_result─│                       │
   │<───Event: memory_start──│                       │
   │<───Event: memory_result─│                       │
   │<───Event: order_placed──│                       │
```

## Real-time UI Components

### 1. Agent Status Cards

Three cards showing live agent status:
- **Vision Agent** - Gemini 3 Flash analysis with code execution results
- **Memory Agent** - AlloyDB ScaNN search with match details
- **Action Agent** - Autonomous order placement

States: `idle` → `thinking` → `success` / `error`

### 2. Progress Timeline

Horizontal 5-phase progress bar:
1. Upload
2. Discovery
3. Vision
4. Memory
5. Action

### 3. Chat Timeline

Scrollable real-time event log with:
- Timestamped messages from all agents
- Color-coded icons
- Expandable details
- Auto-scroll to latest

## WebSocket Events

The backend emits these events during workflow execution:

```javascript
{
  "type": "upload_complete",
  "message": "Image uploaded successfully",
  "timestamp": 1234567890
}

{
  "type": "discovery_start",
  "agent": "vision",
  "message": "Discovering Vision Agent via A2A..."
}

{
  "type": "vision_complete",
  "message": "Analysis complete",
  "result": "Found 15 items",
  "code_output": "# Python code executed..."
}

{
  "type": "memory_complete",
  "part": "Industrial Widget X-9",
  "supplier": "Acme Corp",
  "confidence": "98.5%"
}

{
  "type": "order_placed",
  "order_id": "#9921",
  "message": "Order placed autonomously"
}
```

## File Structure

```
frontend/
├── app.py              # FastAPI server with WebSocket support
├── requirements.txt    # Python dependencies
├── static/
│   ├── index.html     # Single-page application
│   └── app.js         # Alpine.js state management + WebSocket client
└── README.md          # This file
```

## Running the Frontend

### Quick Start

Use the master run script:
```bash
cd ..
sh run.sh
```

### Manual Start

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080
```

Then open http://localhost:8080

## Environment Variables

```bash
# Required for Vertex AI (vision agent)
export GOOGLE_CLOUD_PROJECT=your-project-id

# Agent URLs (defaults to localhost)
export VISION_AGENT_URL=http://localhost:8081
export SUPPLIER_AGENT_URL=http://localhost:8082
```

## API Endpoints

### REST Endpoints

- `GET /` - Serves the HTML UI
- `GET /api/health` - Health check
- `POST /api/analyze` - Upload image, trigger workflow
- `GET /static/*` - Static files (HTML, JS)

### WebSocket Endpoint

- `WS /ws` - Real-time event stream

## Development

### Adding New Events

1. Emit from backend (`app.py`):
```python
await manager.broadcast({
    "type": "custom_event",
    "message": "Something happened",
    "data": {...}
})
```

2. Handle in frontend (`app.js`):
```javascript
case 'custom_event':
    // Update UI state
    this.addMessage('System', data.message, timestamp);
    break;
```

### Styling

Tailwind CSS classes are applied inline:
- `bg-gray-900` - Dark background
- `text-blue-400` - Accent color
- `border-2` - Borders
- `rounded-lg` - Rounded corners

Custom animations in `<style>` block of `index.html`.

## A2A Integration

The frontend acts as an A2A client:

```python
from a2a.client import A2ACardResolver, A2AClient

# Discover agent
resolver = A2ACardResolver(httpx_client=client, base_url=VISION_URL)
card = await resolver.get_agent_card()

# Create client
agent_client = A2AClient(httpx_client=client, agent_card=card)

# Send message
response = await agent_client.send_message(request)
```

## Troubleshooting

### Port 8080 already in use

```bash
lsof -ti:8080 | xargs kill -9
```

### WebSocket disconnects

Check browser console for errors. The UI auto-reconnects after 3 seconds.

### Agents not responding

Verify agents are running:
```bash
curl http://localhost:8081/health
curl http://localhost:8082/health
```

### Image upload fails

Check:
1. File size < 10MB
2. File type is image/* (jpg, png, jpeg)
3. Browser console for JavaScript errors

## Browser Support

- Chrome 90+ (recommended)
- Firefox 88+
- Safari 14+
- Edge 90+

Requires:
- WebSocket support
- ES6+ JavaScript
- CSS Grid

## Performance

- WebSocket events: < 10ms latency
- Image upload: < 1s for typical 2MB files
- UI updates: 60 FPS with hardware acceleration

## Learn More

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Alpine.js Guide](https://alpinejs.dev)
- [WebSockets API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [Tailwind CSS](https://tailwindcss.com)
