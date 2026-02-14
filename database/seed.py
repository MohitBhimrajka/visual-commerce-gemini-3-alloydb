"""
Execute seed_data.sql and insert sample inventory rows.
Run after Auth Proxy is connected. Requires DB_PASS in environment.
"""
import os
import random
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv, find_dotenv
import psycopg2

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

SCRIPT_DIR = Path(__file__).parent
SEED_SQL = SCRIPT_DIR / "seed_data.sql"

SAMPLE_PARTS = [
    ("Cardboard Shipping Box Large", "Packaging Solutions Inc", "Heavy-duty corrugated cardboard shipping container", 250),
    ("Warehouse Storage Container", "Industrial Supply Co", "Stackable plastic storage bin with lid", 180),
    ("Product Shipping Boxes", "Acme Packaging", "Medium corrugated boxes for warehouse storage", 320),
    ("Industrial Widget X-9", "Acme Corp", "Heavy-duty industrial coupling", 50),
    ("Precision Bolt M4", "Global Fasteners Inc", "Stainless steel allen bolt", 200),
    ("Hexagonal Nut M6", "Metro Supply Co", "Galvanized steel nut", 150),
    ("Phillips Head Screw 3x20", "Acme Corp", "Zinc-plated wood screw", 500),
    ("Wooden Dowel 10mm", "Craft Materials Ltd", "Hardwood dowel rod", 80),
    ("Rubber Gasket Small", "SealTech Industries", "Buna-N gasket", 120),
    ("Spring Tension 5kg", "Mechanical Parts Co", "Compression spring", 60),
    ("Bearing 6204", "Bearings Direct", "Deep groove ball bearing", 45),
    ("Warehouse Shelf Boxes", "Storage Systems Ltd", "Standardized warehouse inventory boxes", 400),
    ("Inventory Container Units", "Supply Chain Pros", "Modular storage units for warehouse", 95),
]


def generate_real_embedding(text: str) -> list[float]:
    """Generate real semantic embedding using Google Gen AI SDK."""
    from google import genai
    from google.genai.types import EmbedContentConfig
    
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
    
    # Initialize Gen AI client with Vertex AI
    client = genai.Client(
        vertexai=True,
        project=project,
        location="us-central1"
    )
    
    # Generate embedding using gemini-embedding-001 (768 dimensions)
    response = client.models.embed_content(
        model="text-embedding-005",  # 768 dimensions, optimized for English/code
        contents=[text],
        config=EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768
        )
    )
    
    return response.embeddings[0].values


def main():
    db_pass = os.environ.get("DB_PASS")
    if not db_pass:
        print("Error: DB_PASS environment variable not set.")
        print("Export your database password: export DB_PASS='<your-password>'")
        sys.exit(1)

    # Retry connection up to 3 times (Auth Proxy may need time to initialize)
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Connecting to AlloyDB (attempt {attempt}/{max_retries})...")
            conn = psycopg2.connect(
                host="127.0.0.1",
                port=5432,
                user="postgres",
                password=db_pass,
                dbname="postgres",
                connect_timeout=10,
            )
            print("✅ Connected to database")
            break
        except psycopg2.OperationalError as e:
            if attempt < max_retries:
                print(f"⚠️  Connection failed, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Failed to connect after {max_retries} attempts")
                print(f"Error: {e}")
                print("\nTroubleshooting:")
                print("  1. Check Auth Proxy is running: ps aux | grep alloydb-auth-proxy")
                print("  2. Check proxy logs: tail -50 proxy.log")
                print("  3. Verify password is correct")
                print("  4. Try manually: psql -h 127.0.0.1 -U postgres -d postgres")
                sys.exit(1)

    try:
        # Execute schema from seed_data.sql
        with open(SEED_SQL) as f:
            schema_sql = f.read()
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()

        # Clear existing data for idempotent re-runs
        with conn.cursor() as cur:
            cur.execute("TRUNCATE inventory RESTART IDENTITY;")
        conn.commit()

        # Insert sample rows with REAL semantic embeddings (REQUIRED)
        print("Generating semantic embeddings via Vertex AI...")
        print("(Parallelizing requests - should complete in ~10 seconds)")
        
        # Generate all embeddings in parallel
        def generate_embedding_task(item):
            """Generate embedding for a single item."""
            i, (part_name, supplier_name, description, stock) = item
            text_to_embed = f"{part_name}. {description}"
            print(f"  [{i+1}/{len(SAMPLE_PARTS)}] Embedding: {part_name}...")
            try:
                embedding_values = generate_real_embedding(text_to_embed)
                return (i, part_name, supplier_name, description, stock, embedding_values, None)
            except Exception as e:
                return (i, part_name, supplier_name, description, stock, None, str(e))
        
        # Use ThreadPoolExecutor for parallel API calls
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            futures = {
                executor.submit(generate_embedding_task, (i, item)): i 
                for i, item in enumerate(SAMPLE_PARTS)
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                results.append(future.result())
        
        # Sort results by original index to maintain order
        results.sort(key=lambda x: x[0])
        
        # Insert all results into database
        with conn.cursor() as cur:
            for i, part_name, supplier_name, description, stock, embedding_values, error in results:
                if error:
                    print(f"    ❌ Failed to generate embedding for {part_name}: {error}")
                    print(f"    Skipping {part_name}")
                    continue
                
                vec = "[" + ",".join(str(v) for v in embedding_values) + "]"
                cur.execute(
                    """
                    INSERT INTO inventory (part_name, supplier_name, description, stock_level, part_embedding)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    """,
                    (part_name, supplier_name, description, stock, vec),
                )
        
        conn.commit()
        print("✅ Semantic embeddings generated")

        # Create ScaNN index (after data exists)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_scann
                ON inventory USING scann (part_embedding cosine)
                WITH (num_leaves=5, quantizer='sq8');
            """)
        conn.commit()

        print("Seed complete. Sample rows inserted, ScaNN index created.")
    except Exception as e:
        conn.rollback()
        print(f"Seed failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
