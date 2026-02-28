"""
Backup seeding script: Execute seed_data.sql and optionally insert sample inventory.
Primary path: Run SQL directly in AlloyDB Studio (see codelab).
This script is for convenience if you prefer programmatic seeding.
Requires: ALLOYDB_INSTANCE_URI and DB_PASS in environment.
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
import pg8000
from google.cloud.alloydbconnector import Connector

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

SCRIPT_DIR = Path(__file__).parent
SEED_SQL = SCRIPT_DIR / "seed_data.sql"

# Initialize AlloyDB Connector
connector = Connector()


def get_connection():
    """Connect to AlloyDB via the Python Connector."""
    inst_uri = os.environ.get("ALLOYDB_INSTANCE_URI", "")
    if not inst_uri:
        print("Error: ALLOYDB_INSTANCE_URI not set.")
        print("Format: projects/PROJECT/locations/REGION/clusters/CLUSTER/instances/INSTANCE")
        sys.exit(1)

    return connector.connect(
        inst_uri,
        "pg8000",
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASS", ""),
        db=os.environ.get("DB_NAME", "postgres"),
        ip_type="PUBLIC",
    )


def main():
    db_pass = os.environ.get("DB_PASS")
    if not db_pass:
        print("Error: DB_PASS environment variable not set.")
        print("Export your database password: export DB_PASS='<your-password>'")
        sys.exit(1)

    # Retry connection up to 3 times
    max_retries = 3
    retry_delay = 5

    conn = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Connecting to AlloyDB (attempt {attempt}/{max_retries})...")
            conn = get_connection()
            print("✅ Connected to database")
            break
        except Exception as e:
            if attempt < max_retries:
                print(f"⚠️  Connection failed, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Failed to connect after {max_retries} attempts")
                print(f"Error: {e}")
                print("\nTroubleshooting:")
                print("  1. Check ALLOYDB_INSTANCE_URI is correct")
                print("  2. Verify Public IP is enabled on the instance")
                print("  3. Check DB_PASS is correct")
                print("  4. Ensure you have AlloyDB Client IAM role")
                sys.exit(1)

    try:
        # Read and execute seed SQL
        with open(SEED_SQL) as f:
            sql_content = f.read()

        # pg8000 doesn't support multi-statement execution directly,
        # so split by semicolons and execute each statement
        cursor = conn.cursor()
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]

        for i, stmt in enumerate(statements):
            # Skip comments-only statements
            lines = [l for l in stmt.split('\n') if l.strip() and not l.strip().startswith('--')]
            if not lines:
                continue
            try:
                cursor.execute(stmt)
                conn.commit()
                print(f"  ✅ Statement {i+1}/{len(statements)} executed")
            except Exception as e:
                print(f"  ⚠️  Statement {i+1} failed: {e}")
                conn.rollback()

        # Verify
        cursor.execute("SELECT COUNT(*) FROM inventory")
        count = cursor.fetchone()[0]
        print(f"\n✅ Seed complete. {count} rows in inventory table.")

        cursor.execute("SELECT COUNT(*) FROM inventory WHERE part_embedding IS NOT NULL")
        emb_count = cursor.fetchone()[0]
        print(f"   {emb_count} rows have embeddings.")

    except Exception as e:
        print(f"Seed failed: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
        connector.close()


if __name__ == "__main__":
    main()
