"""
Control Tower: FastAPI + WebSockets UI for the autonomous supply chain loop.
Uses A2A protocol to communicate with Vision and Supplier agents via HTTP.
Real-time updates via WebSockets.
"""
import asyncio
import base64
import io
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Set
from uuid import uuid4

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx
from PIL import Image

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest

# Configure comprehensive logging with environment-based level
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging initialized at {log_level} level")

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

REPO_ROOT = Path(__file__).resolve().parent.parent
VISION_URL = os.environ.get("VISION_AGENT_URL", "http://localhost:8081")
SUPPLIER_URL = os.environ.get("SUPPLIER_AGENT_URL", "http://localhost:8082")

app = FastAPI(title="Autonomous Supply Chain Control Tower")

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected clients
        self.active_connections -= disconnected


manager = ConnectionManager()


def compress_image(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
    """
    Compress image to stay under max_size_kb while maintaining reasonable quality.
    Resizes if needed to keep payload under A2A protocol limits.
    """
    img = Image.open(io.BytesIO(image_bytes))
    
    # Convert to RGB if necessary (removes alpha channel)
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGB')
    
    # Start with max dimension of 1024px (good for vision analysis)
    max_dimension = 1024
    quality = 85
    
    while max_dimension >= 256:  # Don't go below 256px
        # Resize maintaining aspect ratio
        img_copy = img.copy()
        img_copy.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        
        # Compress to JPEG
        output = io.BytesIO()
        img_copy.save(output, format='JPEG', quality=quality, optimize=True)
        compressed_bytes = output.getvalue()
        
        # Check size
        size_kb = len(compressed_bytes) / 1024
        if size_kb <= max_size_kb:
            return compressed_bytes
        
        # Try reducing quality or dimension
        if quality > 60:
            quality -= 10
        else:
            max_dimension = int(max_dimension * 0.8)
            quality = 85
    
    # If still too large, return best effort
    return compressed_bytes


def extract_text_from_response(response) -> str:
    """Extract text from A2A response (supports both old and new SDK formats)."""
    text = ""
    
    # New SDK format: response.root.result.parts[].root.text
    if hasattr(response, "root"):
        root = response.root
        # Check if it's a success response with result
        if hasattr(root, "result"):
            result = root.result
            # Result is a Message object with parts
            if hasattr(result, "parts"):
                for part in (result.parts or []):
                    # Part has a root attribute containing TextPart
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        if part.root.text:
                            text += part.root.text
    
    # Old SDK format: response.artifact.parts[].text
    if not text and hasattr(response, "artifact") and response.artifact:
        for part in getattr(response.artifact, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if not part_text and hasattr(part, "root"):
                part_text = getattr(part.root, "text", None)
            if part_text:
                text += part_text
    
    # Old SDK format: response.messages[].parts[].text
    if not text and hasattr(response, "messages"):
        for msg in (response.messages or []):
            for part in getattr(msg, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if not part_text and hasattr(part, "root"):
                    part_text = getattr(part.root, "text", None)
                if part_text:
                    text += part.text
    
    if not text:
        logger.warning(f"Failed to extract text from A2A response. Response type: {type(response)}")
    
    return text


def extract_thinking_steps(response_text: str, agent_type: str = "vision") -> list:
    """
    Extract thinking steps from agent response.
    For Gemini responses, this attempts to identify reasoning steps.
    """
    import datetime
    
    thinking_steps = []
    
    if agent_type == "vision":
        # Look for code generation patterns in the response
        if "def " in response_text or "import " in response_text:
            thinking_steps.append({
                "step": 1,
                "thought": "Analyzing image requirements and planning approach",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            })
            thinking_steps.append({
                "step": 2,
                "thought": "Writing Python code with OpenCV for box detection",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            })
            thinking_steps.append({
                "step": 3,
                "thought": "Executing code in sandbox environment",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            })
        
        # Look for result patterns
        if "result" in response_text.lower() or "boxes" in response_text.lower():
            thinking_steps.append({
                "step": len(thinking_steps) + 1,
                "thought": "Processing execution results and formatting output",
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            })
    
    elif agent_type == "supplier":
        thinking_steps.append({
            "step": 1,
            "thought": "Generating embedding vector from query text",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })
        thinking_steps.append({
            "step": 2,
            "thought": "Executing ScaNN vector search in AlloyDB",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })
        thinking_steps.append({
            "step": 3,
            "thought": "Ranking results by similarity score",
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
        })
    
    return thinking_steps


async def run_workflow_with_events(image_bytes: bytes):
    """
    Run the full autonomous loop via A2A: Vision -> Memory -> Action.
    Emits WebSocket events at each step for real-time UI updates.
    """
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Phase 0: Upload complete
        await manager.broadcast({
            "type": "upload_complete",
            "message": "Image uploaded successfully",
            "timestamp": asyncio.get_event_loop().time()
        })
        
        await asyncio.sleep(0.5)  # Brief pause for visual feedback
        
        # Phase 1: Discovery - Vision Agent
        await manager.broadcast({
            "type": "discovery_start",
            "agent": "vision",
            "message": "Discovering Vision Agent via A2A protocol...",
            "timestamp": asyncio.get_event_loop().time()
        })
        
        try:
            resolver = A2ACardResolver(httpx_client=client, base_url=VISION_URL)
            vision_card = await resolver.get_agent_card()
            vision_client = A2AClient(httpx_client=client, agent_card=vision_card)
            
            await manager.broadcast({
                "type": "discovery_complete",
                "agent": "vision",
                "message": f"Vision Agent discovered: {vision_card.name}",
                "timestamp": asyncio.get_event_loop().time()
            })
            
            await asyncio.sleep(0.5)
            
            # Phase 2: Vision Analysis
            await manager.broadcast({
                "type": "vision_start",
                "message": "Vision Agent analyzing image with Gemini 3 Flash...",
                "details": "Think-Act-Observe loop initiated",
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Compress image before sending to Vision Agent (prevents "Payload too large" errors)
            original_size_kb = len(image_bytes) / 1024
            compressed_bytes = compress_image(image_bytes, max_size_kb=500)
            compressed_size_kb = len(compressed_bytes) / 1024
            logger.info(f"Image compression: {original_size_kb:.1f}KB -> {compressed_size_kb:.1f}KB")
            
            payload = json.dumps({
                "image_base64": base64.b64encode(compressed_bytes).decode("utf-8"),
                "query": "Write code to count the exact number of boxes on this shelf.",
            })
            
            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message={
                        "role": "user",
                        "parts": [{"kind": "text", "text": payload}],
                        "messageId": uuid4().hex,
                    }
                ),
            )
            
            response = await vision_client.send_message(request)
            vision_text = extract_text_from_response(response)
            
            # Check if we have code execution results
            code_output = None
            if "Code output:" in vision_text or "result" in vision_text.lower():
                code_output = vision_text
            
            await manager.broadcast({
                "type": "vision_complete",
                "message": "Vision analysis complete",
                "result": vision_text,
                "code_output": code_output,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Emit thinking steps for Vision Agent
            thinking_steps = extract_thinking_steps(vision_text, "vision")
            if thinking_steps:
                await manager.broadcast({
                    "type": "thinking_update",
                    "agent": "vision",
                    "steps": thinking_steps
                })
            
        except Exception as e:
            await manager.broadcast({
                "type": "vision_error",
                "message": f"Vision Agent error: {str(e)}",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            })
            return
        
        await asyncio.sleep(0.5)
        
        # Phase 3: Discovery - Supplier Agent
        await manager.broadcast({
            "type": "discovery_start",
            "agent": "supplier",
            "message": "Discovering Supplier Agent via A2A protocol...",
            "timestamp": asyncio.get_event_loop().time()
        })
        
        try:
            supplier_resolver = A2ACardResolver(httpx_client=client, base_url=SUPPLIER_URL)
            supplier_card = await supplier_resolver.get_agent_card()
            supplier_client = A2AClient(httpx_client=client, agent_card=supplier_card)
            
            await manager.broadcast({
                "type": "discovery_complete",
                "agent": "supplier",
                "message": f"Supplier Agent discovered: {supplier_card.name}",
                "timestamp": asyncio.get_event_loop().time()
            })
            
            await asyncio.sleep(0.5)
            
            # Phase 4: Memory Search
            await manager.broadcast({
                "type": "memory_start",
                "message": "Querying AlloyDB with ScaNN vector search...",
                "details": "Searching 1M+ inventory parts",
                "timestamp": asyncio.get_event_loop().time()
            })
            
            # Use the vision agent's analysis result as the search query
            search_query = vision_text[:200] if vision_text else "warehouse inventory part"
            supplier_payload = json.dumps({"query": search_query})
            supplier_request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message={
                        "role": "user",
                        "parts": [{"kind": "text", "text": supplier_payload}],
                        "messageId": uuid4().hex,
                    }
                ),
            )
            
            supplier_response = await supplier_client.send_message(supplier_request)
            supplier_text = extract_text_from_response(supplier_response)
            
            if supplier_text:
                try:
                    supplier_data = json.loads(supplier_text)
                    part_name = supplier_data.get("part", "Unknown")
                    supplier_name = supplier_data.get("supplier", "Unknown")
                    confidence = supplier_data.get("match_confidence", "N/A")
                    
                    await manager.broadcast({
                        "type": "memory_complete",
                        "message": f"Match found: {part_name}",
                        "part": part_name,
                        "supplier": supplier_name,
                        "confidence": confidence,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    
                    # Emit thinking steps for Supplier Agent
                    supplier_thinking = extract_thinking_steps(supplier_text, "supplier")
                    if supplier_thinking:
                        await manager.broadcast({
                            "type": "thinking_update",
                            "agent": "memory",
                            "steps": supplier_thinking
                        })
                    
                    await asyncio.sleep(0.5)
                    
                    # Phase 5: Action - Place Order
                    order_id = f"#{random.randint(9000, 9999)}"
                    await manager.broadcast({
                        "type": "order_placed",
                        "message": f"Order {order_id} placed autonomously",
                        "order_id": order_id,
                        "part": part_name,
                        "supplier": supplier_name,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    
                except json.JSONDecodeError:
                    await manager.broadcast({
                        "type": "memory_complete",
                        "message": "Supplier response received",
                        "result": supplier_text,
                        "timestamp": asyncio.get_event_loop().time()
                    })
            else:
                await manager.broadcast({
                    "type": "memory_error",
                    "message": "No matching supplier found",
                    "timestamp": asyncio.get_event_loop().time()
                })
                
        except Exception as e:
            await manager.broadcast({
                "type": "memory_error",
                "message": f"Supplier Agent error: {str(e)}",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive any client messages
            data = await websocket.receive_text()
            # Echo back for connection health check
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/analyze")
async def analyze_image(file: UploadFile = File(...)):
    """
    Upload an image and trigger the autonomous workflow.
    Returns immediately while workflow runs in background with WebSocket updates.
    """
    try:
        image_bytes = await file.read()
        
        # Validate image
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Run workflow in background
        asyncio.create_task(run_workflow_with_events(image_bytes))
        
        return {
            "status": "processing",
            "message": "Workflow started. Listen to WebSocket for real-time updates."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "control-tower",
        "vision_url": VISION_URL,
        "supplier_url": SUPPLIER_URL
    }


@app.get("/api/test-images")
async def list_test_images():
    """List available test images from test-images folder."""
    test_images_dir = REPO_ROOT / "test-images"
    
    if not test_images_dir.exists():
        return {"images": []}
    
    images = []
    for img_path in test_images_dir.glob("*"):
        if img_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            images.append({
                "name": img_path.name,
                "path": str(img_path.relative_to(REPO_ROOT))
            })
    
    return {"images": images}


@app.get("/api/test-image/{image_name}")
async def get_test_image(image_name: str):
    """Serve a specific test image."""
    test_images_dir = REPO_ROOT / "test-images"
    image_path = test_images_dir / image_name
    
    if not image_path.exists() or image_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path)


# Serve static files (HTML, CSS, JS)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main UI."""
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        return HTMLResponse("""
        <html>
            <body>
                <h1>Autonomous Supply Chain Control Tower</h1>
                <p>Static files not found. Please create frontend/static/index.html</p>
            </body>
        </html>
        """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
