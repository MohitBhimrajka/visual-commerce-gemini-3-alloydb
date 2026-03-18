"""
Supplier Agent: AlloyDB vector search for finding parts and suppliers.
Uses ScaNN (<=> cosine distance) for high-speed semantic retrieval.
Connects via AlloyDB Python Connector (no Auth Proxy needed).
"""
import base64
import json
import logging
import os
import tempfile
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


def _init_connector():
    """Initialize AlloyDB Connector, optionally using a shared service account key."""
    creds = None

    # Option 1: Base64-encoded SA key (for Cloud Run env vars)
    sa_key_b64 = os.environ.get("ALLOYDB_SA_KEY_B64", "")
    # Option 2: Path to SA key JSON file (for local/Cloud Shell)
    sa_key_path = os.environ.get("ALLOYDB_SA_KEY_PATH", "")

    if sa_key_b64:
        from google.oauth2 import service_account
        key_data = json.loads(base64.b64decode(sa_key_b64))
        creds = service_account.Credentials.from_service_account_info(key_data)
        logger.info("AlloyDB Connector: using shared SA key (base64)")
    elif sa_key_path:
        # Resolve relative paths against the .env file's directory (repo root)
        if not os.path.isabs(sa_key_path):
            env_file = find_dotenv(usecwd=True)
            if env_file:
                sa_key_path = os.path.join(os.path.dirname(env_file), sa_key_path)
        if os.path.exists(sa_key_path):
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(sa_key_path)
            logger.info(f"AlloyDB Connector: using shared SA key ({sa_key_path})")
        else:
            logger.warning(f"AlloyDB Connector: SA key not found at {sa_key_path}, falling back to ADC")
    else:
        logger.info("AlloyDB Connector: using Application Default Credentials")

    return Connector(credentials=creds, refresh_strategy="lazy")


# Initialize connector once (reuse across requests)
connector = _init_connector()


def get_connection():
    """Connect to AlloyDB via the Python Connector (IAM-authenticated, no proxy needed)."""
    # Build instance URI from component env vars (or use pre-built if set)
    inst_uri = os.environ.get("ALLOYDB_INSTANCE_URI", "")
    if not inst_uri:
        # ALLOYDB_PROJECT allows cross-project connections (shared instance scenarios)
        # Falls back to GOOGLE_CLOUD_PROJECT for single-project setups
        project = os.environ.get("ALLOYDB_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", ""))
        region = os.environ.get("ALLOYDB_REGION", "")
        cluster = os.environ.get("ALLOYDB_CLUSTER", "")
        instance = os.environ.get("ALLOYDB_INSTANCE", "")
        if project and region and cluster and instance:
            inst_uri = f"projects/{project}/locations/{region}/clusters/{cluster}/instances/{instance}"
        else:
            raise ValueError(
                "AlloyDB not configured. Set ALLOYDB_REGION, ALLOYDB_CLUSTER, "
                "and ALLOYDB_INSTANCE in your .env file."
            )

    conn = connector.connect(
        inst_uri,
        "pg8000",
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASS", ""),
        db=os.environ.get("DB_NAME", "postgres"),
        ip_type=os.environ.get("ALLOYDB_IP_TYPE", "PUBLIC"),
    )
    return conn


def find_supplier(embedding_vector: list[float]) -> tuple | None:
    """
    Find the nearest supplier for the given part embedding using ScaNN.
    """
    logger.info(f"Searching inventory with embedding (dimension: {len(embedding_vector)})")

    # pg8000 converts Python lists to PostgreSQL array format {0.1,0.1,...}
    # but pgvector expects [0.1,0.1,...] — so we convert to string first
    embedding_str = "[" + ",".join(str(v) for v in embedding_vector) + "]"

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
