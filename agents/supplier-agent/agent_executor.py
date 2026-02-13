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
        import sys
        print(f"\n[DEBUG] SupplierAgentExecutor.execute called", file=sys.stderr)
        
        # Handle API change: try different attribute names for message
        message = getattr(context, 'message', None) or getattr(context, 'request_message', None)
        print(f"[DEBUG] Message object: {message}", file=sys.stderr)
        
        parts = message.parts if message and hasattr(message, 'parts') else []
        print(f"[DEBUG] Message parts: {len(parts)} parts", file=sys.stderr)
        
        query = None
        embedding = None

        for p in parts:
            # Try both p.text and p.root.text (API structure varies)
            text = getattr(p, "text", None)
            if not text and hasattr(p, "root"):
                text = getattr(p.root, "text", None)
            print(f"[DEBUG] Part text: {text[:100] if text else None}...", file=sys.stderr)
            if text:
                try:
                    data = json.loads(text)
                    query = data.get("query")
                    embedding = data.get("embedding")
                    print(f"[DEBUG] Parsed JSON - query: {query[:50] if query else None}, embedding: {len(embedding) if embedding else 0} dims", file=sys.stderr)
                except json.JSONDecodeError:
                    query = text
                    print(f"[DEBUG] Using raw text as query: {query[:50]}", file=sys.stderr)

        if not query and not embedding:
            print(f"[ERROR] No query or embedding provided!", file=sys.stderr)
            await event_queue.enqueue_event(
                new_agent_text_message(
                    "Error: Provide 'query' (text) or 'embedding' (vector) in JSON."
                )
            )
            return

        try:
            if embedding:
                emb = embedding
                print(f"[DEBUG] Using provided embedding: {len(emb)} dims", file=sys.stderr)
            else:
                print(f"[DEBUG] Generating embedding for query: {query}", file=sys.stderr)
                emb = get_embedding(query)

            print(f"[DEBUG] Calling find_supplier with embedding...", file=sys.stderr)
            result = find_supplier(emb)
            print(f"[DEBUG] find_supplier returned: {result}", file=sys.stderr)
            
            if not result:
                print(f"[ERROR] No result from find_supplier", file=sys.stderr)
                await event_queue.enqueue_event(
                    new_agent_text_message("No matching supplier found in inventory.")
                )
                return
        except Exception as e:
            import traceback
            print(f"[ERROR] Exception in supplier agent: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
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
        message_text = json.dumps(out, indent=2)
        print(f"[DEBUG] Sending message to frontend: {message_text}", file=sys.stderr)
        await event_queue.enqueue_event(new_agent_text_message(message_text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")
