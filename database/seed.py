"""
Execute seed_data.sql and insert sample inventory rows.
Run after Auth Proxy is connected. Requires DB_PASS in environment.
"""
import os
import random
import sys
import time
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
import psycopg2

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

SCRIPT_DIR = Path(__file__).parent
SEED_SQL = SCRIPT_DIR / "seed_data.sql"

SAMPLE_PARTS = [
    ("Industrial Widget X-9", "Acme Corp", "Heavy-duty industrial coupling", 50),
    ("Precision Bolt M4", "Global Fasteners Inc", "Stainless steel allen bolt", 200),
    ("Hexagonal Nut M6", "Metro Supply Co", "Galvanized steel nut", 150),
    ("Phillips Head Screw 3x20", "Acme Corp", "Zinc-plated wood screw", 500),
    ("Wooden Dowel 10mm", "Craft Materials Ltd", "Hardwood dowel rod", 80),
    ("Rubber Gasket Small", "SealTech Industries", "Buna-N gasket", 120),
    ("Spring Tension 5kg", "Mechanical Parts Co", "Compression spring", 60),
    ("Bearing 6204", "Bearings Direct", "Deep groove ball bearing", 45),
]


def generate_vector(dim: int = 768, seed: int | None = None) -> str:
    """Generate a random normalized vector as PostgreSQL vector literal."""
    if seed is not None:
        random.seed(seed)
    values = [random.uniform(-0.5, 0.5) for _ in range(dim)]
    # Normalize for cosine distance (ScaNN <=> operator returns distance, not similarity)
    magnitude = sum(v * v for v in values) ** 0.5
    if magnitude > 0:
        values = [v / magnitude for v in values]
    return "[" + ",".join(str(round(v, 6)) for v in values) + "]"


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

        # Insert sample rows
        with conn.cursor() as cur:
            for i, (part_name, supplier_name, description, stock) in enumerate(SAMPLE_PARTS):
                vec = generate_vector(seed=i)
                cur.execute(
                    """
                    INSERT INTO inventory (part_name, supplier_name, description, stock_level, part_embedding)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    """,
                    (part_name, supplier_name, description, stock, vec),
                )
        conn.commit()

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
