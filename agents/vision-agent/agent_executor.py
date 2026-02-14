"""
Vision Agent Executor: Bridges A2A protocol to Gemini 3 Flash.
"""
import asyncio
import base64
import json
import logging
import os
import sys

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


def _detect_bounding_boxes(image_bytes: bytes) -> str:
    """
    Detect bounding boxes using Gemini 3 Flash spatial understanding.
    Runs as a sync function (called via asyncio.to_thread for parallelism).
    Returns JSON string of bounding boxes array.
    """
    try:
        from google import genai
        from google.genai import types

        gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        bbox_system_instructions = """
            Return bounding boxes as a JSON array with labels. Never return masks or code fencing. Limit to 25 objects.
            If an object is present multiple times, name them according to their unique characteristic (colors, size, position, unique characteristics, etc..).
        """

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        bbox_response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                "Detect the 2d bounding boxes of all the items/boxes/objects on the shelf or in the image. Label each with a short description.",
                image_part,
            ],
            config=types.GenerateContentConfig(
                system_instruction=bbox_system_instructions,
                temperature=0.5,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
        )

        bbox_text = bbox_response.text.strip()
        # Strip markdown code fencing if present
        if bbox_text.startswith("```json"):
            bbox_text = bbox_text[7:]
        if bbox_text.startswith("```"):
            bbox_text = bbox_text[3:]
        if bbox_text.endswith("```"):
            bbox_text = bbox_text[:-3]
        bbox_text = bbox_text.strip()

        # Validate it's valid JSON
        parsed_boxes = json.loads(bbox_text)
        logger.info(f"Detected {len(parsed_boxes)} bounding boxes")
        return json.dumps(parsed_boxes)

    except Exception as e:
        logger.warning(f"Bounding box detection failed: {e}")
        return "[]"


class VisionAgentExecutor(AgentExecutor):
    """A2A executor that delegates to Gemini 3 Flash for image analysis."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info("=" * 80)
        logger.info("VISION AGENT EXECUTOR - EXECUTE CALLED")
        logger.info(f"Context type: {type(context)}")
        logger.info("=" * 80)

        # Handle API change: try different attribute names for message
        message = getattr(context, 'message', None) or getattr(context, 'request_message', None)
        logger.info(f"Message extracted: {message is not None}")

        parts = message.parts if message and hasattr(message, 'parts') else []
        logger.info(f"Message has {len(parts)} part(s)")

        image_base64 = None
        query = "Write code to count the exact number of boxes on this shelf."

        for i, p in enumerate(parts):
            logger.info(f"Processing part {i+1}...")
            # Try both p.text and p.root.text (API structure varies)
            text = getattr(p, "text", None)
            if not text and hasattr(p, "root"):
                text = getattr(p.root, "text", None)
            if text:
                try:
                    data = json.loads(text)
                    image_base64 = data.get("image_base64")
                    query = data.get("query", query)
                except json.JSONDecodeError:
                    query = text

        if not image_base64:
            logger.error("No image_base64 found in message parts")
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Error: No image. Send JSON: {\"image_base64\": \"<base64>\", \"query\": \"...\"}"
                )
            )
            return

        logger.info(f"Image base64 length: {len(image_base64)} chars")
        logger.info(f"Query: {query[:100]}...")

        try:
            logger.info("Decoding base64 image...")
            image_bytes = base64.b64decode(image_base64)
            logger.info(f"Decoded image size: {len(image_bytes)} bytes")
        except Exception as e:
            logger.error(f"Error decoding base64 image: {e}", exc_info=True)
            await event_queue.enqueue_event(new_agent_text_message(f"Error decoding image: {e}"))
            return

        # Run analyze_image AND bounding box detection IN PARALLEL
        # analyze_image: ~90-120s (Gemini 3 Flash with code execution)
        # bounding boxes: ~20-25s (Gemini 3 Flash spatial understanding, thinking_budget=0)
        # Total time = max(analyze, bbox) instead of analyze + bbox
        logger.info("Starting parallel: analyze_image + bounding box detection...")

        analyze_task = asyncio.to_thread(analyze_image, image_bytes, query)
        bbox_task = asyncio.to_thread(_detect_bounding_boxes, image_bytes)

        try:
            result, bounding_boxes_json = await asyncio.gather(analyze_task, bbox_task)
            logger.info("Both parallel tasks completed successfully")
            logger.info(f"Result keys: {list(result.keys())}")
        except Exception as e:
            logger.error("=" * 80)
            logger.error("PARALLEL EXECUTION ERROR")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            logger.error("Full traceback:", exc_info=True)
            logger.error("=" * 80)
            await event_queue.enqueue_event(new_agent_text_message(f"Error analyzing image: {e}"))
            return

        # Build structured response for better downstream processing
        answer = result.get("answer", "No analysis returned.")
        code_output = result.get("code_output", "")

        # Create a comprehensive response
        if code_output:
            full_response = f"Code output: {code_output}\n\n{answer}"
        else:
            full_response = answer

        # Use Gemini 2.5 Flash Lite with structured outputs for semantic search query
        # Fast (~200ms), cheap, dataset-agnostic. No code execution (structured outputs only).
        logger.info("Generating semantic search query with Gemini 2.5 Flash Lite (structured output)...")

        try:
            from google import genai
            from google.genai import types
            from pydantic import BaseModel, Field

            # Structured output schema - predictable, type-safe
            class SearchQueryResult(BaseModel):
                search_query: str = Field(
                    description="3-5 word semantic search query for finding matching inventory items in supplier database. Focus on item type, material, category. Example: 'cardboard shipping boxes warehouse'"
                )

            gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

            query_prompt = f"""Convert this vision analysis into a semantic search query for a supplier/inventory database.

Vision Analysis: {answer}

Create a 3-5 word query that would best match supplier catalog items.
Focus on: item type, material, category, or use case. Ignore quantities.
Works for any dataset - boxes, parts, equipment, etc."""

            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash-lite",  # Fast, cheap, structured output support
                contents=query_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=50,
                    response_mime_type="application/json",
                    response_json_schema=SearchQueryResult.model_json_schema(),
                )
            )

            result = SearchQueryResult.model_validate_json(response.text)
            search_query = result.search_query.strip()
            logger.info(f"Generated search query: {search_query}")

            # Include search query in response
            search_hint = f"\n\nSearch terms: {search_query}"
            full_response += search_hint

        except Exception as e:
            logger.warning(f"Failed to generate search query with LLM: {e}")
            # Fallback: use first 50 chars of answer (basic)
            search_query = answer[:50].strip()
            logger.info(f"Using fallback search query: {search_query}")

        # Append bounding boxes as a tagged section in the response
        full_response += f"\n\n[BOUNDING_BOXES]{bounding_boxes_json}[/BOUNDING_BOXES]"

        logger.info("Vision analysis complete")

        await event_queue.enqueue_event(new_agent_text_message(full_response))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")
