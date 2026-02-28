"""
Supplier Agent: AlloyDB vector search for finding parts and suppliers.
Uses ScaNN (<=> cosine distance) for high-speed semantic retrieval.
Connects via AlloyDB Python Connector (no Auth Proxy needed).
"""
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
import pg8000
from google.cloud.alloydbconnector import Connector

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize AlloyDB Connector once (reuse across requests)
connector = Connector()


def get_connection():
    """Connect to AlloyDB via the Python Connector (IAM-authenticated, no proxy needed)."""
    inst_uri = os.environ.get("ALLOYDB_INSTANCE_URI", "")
    if not inst_uri:
        raise ValueError(
            "ALLOYDB_INSTANCE_URI not set. "
            "Format: projects/PROJECT/locations/REGION/clusters/CLUSTER/instances/INSTANCE"
        )

    conn = connector.connect(
        inst_uri,
        "pg8000",
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASS", ""),
        db=os.environ.get("DB_NAME", "postgres"),
        ip_type="PUBLIC",  # Cloud Shell uses Public IP; change to "PRIVATE" for Cloud Run
    )
    return conn


def find_supplier(embedding_vector: list[float]) -> tuple | None:
    """
    Find the nearest supplier for the given part embedding using ScaNN.
    """
    logger.info(f"Searching inventory with embedding (dimension: {len(embedding_vector)})")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        # ============================================================
        # CODELAB STEP 1: Implement ScaNN Vector Search
        # ============================================================
        # TODO: Replace this placeholder query with ScaNN vector search
        #
        # The <=> operator computes cosine distance between vectors.
        # ORDER BY <=> finds the nearest match (lowest distance).
        # The ScaNN index automatically accelerates this query.

        sql = "SELECT part_name, supplier_name FROM inventory LIMIT 1;"
        cursor.execute(sql)
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise
    finally:
        conn.close()


def get_embedding(text: str) -> list[float]:
    """
    Generate embedding for query text using Vertex AI text-embedding-005.
    """
    from google import genai
    from google.genai.types import EmbedContentConfig

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    logger.debug(f"get_embedding called with text: {text[:50]}...")
    logger.debug(f"Using GCP project: {project}")

    try:
        # Initialize Gen AI client with Vertex AI
        client = genai.Client(
            vertexai=True,
            project=project,
            location="us-central1"
        )

        # Generate embedding using text-embedding-005 (768 dimensions)
        response = client.models.embed_content(
            model="text-embedding-005",
            contents=[text],
            config=EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",  # For query embeddings
                output_dimensionality=768
            )
        )

        embedding_values = response.embeddings[0].values
        logger.info(f"Generated embedding with {len(embedding_values)} dimensions")
        return embedding_values
    except Exception as e:
        logger.error(f"Embedding API failed: {e}")
        raise


def main():
    """Run standalone verification with a test embedding."""
    # Load real pre-computed embedding for "Industrial Widget X-9"
    test_vectors_path = Path(__file__).parent / "test_vectors.json"
    if test_vectors_path.exists():
        with open(test_vectors_path) as f:
            test_data = json.load(f)
            test_embedding = test_data["industrial_widget_x9"]["embedding"]
            print(f"Testing with real embedding for: {test_data['industrial_widget_x9']['description']}")
    else:
        # Fallback to random if file missing (shouldn't happen in normal use)
        import random
        random.seed(42)
        test_embedding = [random.uniform(-0.1, 0.1) for _ in range(768)]
        print("Warning: Using fallback random embedding (test_vectors.json not found)")

    result = find_supplier(test_embedding)
    if result:
        part_name, supplier_name = result[0], result[1]
        distance = result[2] if len(result) > 2 else None
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
