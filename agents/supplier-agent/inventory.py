"""
Supplier Agent: AlloyDB vector search for finding parts and suppliers.
Uses ScaNN (<=> cosine distance) for high-speed semantic retrieval.
"""
import json
import logging
import os

from dotenv import load_dotenv, find_dotenv
import psycopg2
from pgvector.psycopg2 import register_vector

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_connection():
    """Connect to AlloyDB via Auth Proxy (localhost)."""
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        user="postgres",
        password=os.environ.get("DB_PASS", ""),
        dbname="postgres",
    )
    register_vector(conn)
    return conn


def find_supplier(embedding_vector: list[float]) -> tuple | None:
    """
    Find the nearest supplier for the given part embedding using ScaNN.
    """
    logger.info(f"Searching inventory with embedding (dimension: {len(embedding_vector)})")
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # ============================================================
            # CODELAB STEP 1: Implement ScaNN Vector Search
            # ============================================================
            # TODO: Replace this placeholder query with ScaNN vector search
            # 
            # Current behavior: Returns the first row (no similarity matching)
            # Expected behavior: Return the NEAREST match using cosine distance
            # 
            # Hint: Use the <=> operator for cosine distance
            # Hint: ORDER BY distance (ascending = closer match)
            # Hint: PostgreSQL requires explicit cast: %s::vector
            # 
            # See codelab Step 5 for the complete implementation
            # ============================================================
            
            sql = "SELECT part_name, supplier_name FROM inventory LIMIT 1;"
            cursor.execute(sql)
            result = cursor.fetchone()
            
            if result:
                logger.warning("Using placeholder query - returns first row, not nearest match")
            
            return result
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise
    finally:
        conn.close()


def get_embedding(text: str) -> list[float]:
    """
    Generate embedding for query text using Vertex AI text-embedding-005.
    """
    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    logger.debug(f"get_embedding called with text: {text[:50]}...")
    logger.debug(f"Using GCP project: {project}")
    
    try:
        vertexai.init(project=project, location="us-central1")
        model = TextEmbeddingModel.from_pretrained("text-embedding-005")
        embeddings = model.get_embeddings([text])
        embedding_values = embeddings[0].values
        logger.info(f"Generated embedding with {len(embedding_values)} dimensions")
        return embedding_values
    except Exception as e:
        logger.error(f"Vertex AI embedding failed: {e}")
        raise


def main():
    """Run standalone verification with a test embedding."""
    # Use a dummy embedding for standalone test (first row will be returned)
    # In real use, get_embedding("Industrial Widget X-9") would be called
    import random
    random.seed(42)
    test_embedding = [random.uniform(-0.1, 0.1) for _ in range(768)]

    result = find_supplier(test_embedding)
    if result:
        part_name, supplier_name, distance = result
        output = {
            "part": part_name,
            "supplier": supplier_name,
            "distance": float(distance) if distance else 0.0,
            "match_confidence": "99.8%",
        }
        print(json.dumps(output, indent=2))
    else:
        print(json.dumps({"error": "No matching supplier found"}))


if __name__ == "__main__":
    main()
