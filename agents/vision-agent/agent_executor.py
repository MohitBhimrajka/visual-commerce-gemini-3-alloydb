"""
Vision Agent Executor: Bridges A2A protocol to Gemini 3 Flash.
"""
import base64
import json
import logging
import sys

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from agent import analyze_image

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)


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

        logger.info("Calling analyze_image function...")
        try:
            result = analyze_image(image_bytes, query)
            logger.info("analyze_image completed successfully")
            logger.info(f"Result keys: {list(result.keys())}")
        except Exception as e:
            logger.error("=" * 80)
            logger.error("ANALYZE_IMAGE ERROR")
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
        
        # Extract key terms for supplier search (simple keyword extraction)
        # Look for numbers and common inventory terms
        search_terms = []
        import re
        numbers = re.findall(r'\d+', code_output) if code_output else []
        if numbers:
            search_terms.append(f"{numbers[0]} items")
        # Add common inventory keywords from answer
        inventory_keywords = ['box', 'boxes', 'container', 'package', 'unit', 'part', 'item', 'component']
        for keyword in inventory_keywords:
            if keyword in answer.lower():
                search_terms.append(keyword)
                break
        
        # Include search hint in response for better supplier matching
        if search_terms:
            search_hint = f"\n\nSearch terms: {', '.join(search_terms)}"
            full_response += search_hint
            
        import sys
        print(f"[INFO] Vision analysis complete. Search terms: {search_terms if search_terms else 'none'}", file=sys.stderr)
        
        await event_queue.enqueue_event(new_agent_text_message(full_response))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")
