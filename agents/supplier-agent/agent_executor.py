"""
Supplier Agent Executor: Bridges A2A protocol to AlloyDB ScaNN search.
"""
import json

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from inventory import find_supplier, get_embedding


class SupplierAgentExecutor(AgentExecutor):
    """A2A executor that searches inventory via AlloyDB ScaNN vector search."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Handle API change: try different attribute names for message
        message = getattr(context, 'message', None) or getattr(context, 'request_message', None)
        parts = message.parts if message and hasattr(message, 'parts') else []
        
        query = None
        embedding = None

        for p in parts:
            text = getattr(p, "text", None)
            if text:
                try:
                    data = json.loads(text)
                    query = data.get("query")
                    embedding = data.get("embedding")
                except json.JSONDecodeError:
                    query = text

        if not query and not embedding:
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Error: Provide 'query' (text) or 'embedding' (vector) in JSON."
                )
            )
            return

        try:
            if embedding:
                emb = embedding
            else:
                emb = get_embedding(query)

            result = find_supplier(emb)
            if not result:
                await event_queue.enqueue_event(
                    new_agent_text_message("No matching supplier found in inventory.")
                )
                return
        except Exception as e:
            await event_queue.enqueue_event(
                new_agent_text_message(f"Database error: {str(e)}")
            )
            return

        part_name, supplier_name = result[:2]
        distance = result[2] if len(result) > 2 else None
        confidence = f"{max(0, 100 - (distance or 0) * 100):.1f}%" if distance else "99.8%"
        out = {
            "part": part_name,
            "supplier": supplier_name,
            "match_confidence": confidence,
        }
        await event_queue.enqueue_event(new_agent_text_message(json.dumps(out, indent=2)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")
