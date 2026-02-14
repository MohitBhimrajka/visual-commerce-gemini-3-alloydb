"""
Vision Agent Executor: Bridges A2A protocol to Gemini 3 Flash.

Architecture (2 calls):
  1. analyze_image() from agent.py — Gemini 3 Flash + code execution + LOW thinking → plain markdown
  2. Gemini 2.5 Flash Lite — structured output → parses markdown into schema + search query (~1s)
"""
import base64
import json
import logging
import os

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from agent import analyze_image

# Configure logging with environment-based level
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VisionAgentExecutor(AgentExecutor):
    """A2A executor that delegates to Gemini 3 Flash for image analysis."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info("=" * 80)
        logger.info("VISION AGENT EXECUTOR - EXECUTE CALLED")
        logger.info("=" * 80)

        message = getattr(context, 'message', None) or getattr(context, 'request_message', None)
        parts = message.parts if message and hasattr(message, 'parts') else []

        image_base64 = None
        for p in parts:
            text = getattr(p, "text", None)
            if not text and hasattr(p, "root"):
                text = getattr(p.root, "text", None)
            if text:
                try:
                    data = json.loads(text)
                    image_base64 = data.get("image_base64")
                except json.JSONDecodeError:
                    pass

        if not image_base64:
            await event_queue.enqueue_event(
                new_agent_text_message("Error: No image. Send JSON: {\"image_base64\": \"<base64>\"}")
            )
            return

        try:
            image_bytes = base64.b64decode(image_base64)
            logger.info(f"Decoded image: {len(image_bytes)} bytes")
        except Exception as e:
            await event_queue.enqueue_event(new_agent_text_message(f"Error decoding image: {e}"))
            return

        # ── CALL 1: analyze_image() from agent.py ──
        # Gemini 3 Flash + code execution + LOW thinking → plain markdown.
        # This is the function codelab participants edit (uncomment thinking + code execution).
        logger.info("Call 1: analyze_image() — Gemini 3 Flash (code execution + LOW thinking)...")

        try:
            import asyncio
            result = await asyncio.to_thread(analyze_image, image_bytes)
            logger.info(f"Call 1 complete. Result keys: {list(result.keys())}")

            # Build raw text from all result parts
            answer = result.get("answer", "")
            code_output = result.get("code_output", "")
            raw_text = answer
            if code_output:
                raw_text = f"Code output: {code_output}\n\n{answer}"

            logger.info(f"Raw text length: {len(raw_text)} chars")
            if code_output:
                logger.info(f"Code execution output: {code_output[:200]}")

        except Exception as e:
            logger.error(f"analyze_image failed: {e}", exc_info=True)
            await event_queue.enqueue_event(new_agent_text_message(f"Error analyzing image: {e}"))
            return

        # ── CALL 2: Flash Lite — structure everything from raw markdown ──
        # Fast (~1s), cheap. Parses the raw markdown into structured schema.
        # Extracts: count, type, summary, confidence, search_query, AND bounding boxes.
        logger.info("Call 2: Gemini 2.5 Flash Lite (structure raw output)...")

        try:
            from google import genai
            from google.genai import types
            from pydantic import BaseModel, Field

            gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

            class DetectedObject(BaseModel):
                box_2d: list[int] = Field(description="Bounding box [ymin, xmin, ymax, xmax] normalized 0-1000")
                label: str = Field(description="Short label for this object")

            class StructuredVisionResult(BaseModel):
                item_count: int = Field(description="Total number of primary objects detected")
                item_type: str = Field(description="Type of primary objects, e.g. 'cardboard boxes'")
                summary: str = Field(description="One crisp sentence: what was found and how many")
                confidence: str = Field(description="high, medium, or low")
                search_query: str = Field(description="3-5 word semantic search query for supplier database. Focus on item type, material, category.")
                objects: list[DetectedObject] = Field(description="Bounding boxes extracted from the analysis. If none found, return empty array.")

            structure_prompt = f"""Parse this vision analysis output into structured data.
Extract the item count, type, a one-sentence summary, confidence level, a 3-5 word supplier search query, and any bounding boxes (box_2d coordinates).
The item_count must match the number of objects in the objects array.

Vision Analysis Output:
{raw_text}"""

            structure_response = gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=structure_prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_json_schema=StructuredVisionResult.model_json_schema(),
                )
            )

            structured = StructuredVisionResult.model_validate_json(structure_response.text)
            logger.info(f"Structured: {structured.item_count} {structured.item_type}, {len(structured.objects)} bboxes, query='{structured.search_query}'")

            # Ensure count matches objects array
            if structured.item_count != len(structured.objects) and len(structured.objects) > 0:
                logger.warning(f"Count mismatch: item_count={structured.item_count}, objects={len(structured.objects)}. Using objects length.")
                structured.item_count = len(structured.objects)

            summary = structured.summary
            search_query = structured.search_query
            bounding_boxes = [obj.model_dump() for obj in structured.objects]

        except Exception as e:
            logger.warning(f"Flash Lite structuring failed: {e}")
            summary = raw_text[:200].strip()
            search_query = raw_text[:50].strip()
            bounding_boxes = []

        # ── Build response (compatible with frontend app.py parsing) ──
        full_response = f"{summary}\n\nSearch terms: {search_query}"
        full_response += f"\n\n[BOUNDING_BOXES]{json.dumps(bounding_boxes)}[/BOUNDING_BOXES]"

        logger.info("Vision analysis complete")
        await event_queue.enqueue_event(new_agent_text_message(full_response))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")
