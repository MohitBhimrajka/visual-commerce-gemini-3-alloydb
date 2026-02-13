"""
Vision Agent Executor: Bridges A2A protocol to Gemini 3 Flash.
"""
import base64
import json

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from agent import analyze_image


class VisionAgentExecutor(AgentExecutor):
    """A2A executor that delegates to Gemini 3 Flash for image analysis."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Handle API change: try different attribute names for message
        message = getattr(context, 'message', None) or getattr(context, 'request_message', None)
        parts = message.parts if message and hasattr(message, 'parts') else []
        
        image_base64 = None
        query = "Write code to count the exact number of boxes on this shelf."

        for p in parts:
            text = getattr(p, "text", None)
            if text:
                try:
                    data = json.loads(text)
                    image_base64 = data.get("image_base64")
                    query = data.get("query", query)
                except json.JSONDecodeError:
                    query = text

        if not image_base64:
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Error: No image. Send JSON: {\"image_base64\": \"<base64>\", \"query\": \"...\"}"
                )
            )
            return

        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            await event_queue.enqueue_event(new_agent_text_message(f"Error decoding image: {e}"))
            return

        result = analyze_image(image_bytes, query)
        answer = result.get("answer", "No analysis returned.")
        if result.get("code_output"):
            answer = f"Code output: {result['code_output']}\n\n{answer}"
        await event_queue.enqueue_event(new_agent_text_message(answer))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")
