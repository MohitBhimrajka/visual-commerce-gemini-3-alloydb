"""
Supplier Agent: AlloyDB vector search for finding parts and suppliers.
Uses ScaNN (<=> cosine distance) for high-speed semantic retrieval.
"""
import json
import os

from dotenv import load_dotenv, find_dotenv
import psycopg2
from pgvector.psycopg2 import register_vector

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))


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
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # TODO: Replace this placeholder with the ScaNN vector search query.
            # Use the <=> operator for cosine distance on part_embedding.
            # Remember to cast the input parameter to ::vector type.
            sql = """
            SELECT part_name, supplier_name, 0.0 as distance
            FROM inventory
            LIMIT 1;
            """
            cursor.execute(sql)
            return cursor.fetchone()
    finally:
        conn.close()


def get_embedding(text: str) -> list[float]:
    """
    Generate embedding for query text using Vertex AI text-embedding-005.
    """
    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    vertexai.init(project=project, location="us-central1")
    model = TextEmbeddingModel.from_pretrained("text-embedding-005")
    embeddings = model.get_embeddings([text])
    return embeddings[0].values


def main():
    """Run standalone verification with a test embedding."""
    # Use a dummy embedding for standalone test (first row will be returned)
    # In real use, get_embedding("Industrial Widget X-9") would be called
    import random
    random.seed(42)
    test_embedding = [random.uniform(-0.1, 0.1) for _ in range(768)]

    result = find_supplier(test_embedding)
    if result:
        part_name, supplier_name = result
        output = {
            "part": part_name,
            "supplier": supplier_name,
            "match_confidence": "99.8%",
        }
        print(json.dumps(output, indent=2))
    else:
        print(json.dumps({"error": "No matching supplier found"}))


if __name__ == "__main__":
    main()
