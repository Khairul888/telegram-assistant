"""Quick script to check current database state."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase import create_client

    # Get credentials
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if not url or not key:
        print("[ERROR] Missing SUPABASE_URL or SUPABASE_KEY in .env file")
        exit(1)

    # Create client
    supabase = create_client(url, key)

    print("[CHECKING] Supabase Database...\n")

    # Check existing tables and their data
    tables = [
        'trips',
        'expenses',
        'travel_events',
        'documents',
        'user_sessions'
    ]

    for table_name in tables:
        print(f"\n{'='*60}")
        print(f"TABLE: {table_name}")
        print('='*60)

        try:
            # Try to query the table
            result = supabase.table(table_name).select('*').limit(5).execute()

            if result.data:
                print(f"[OK] Table exists with {len(result.data)} row(s) (showing first 5)")
                print(f"\nSample data:")
                for i, row in enumerate(result.data, 1):
                    print(f"\nRow {i}:")
                    for key, value in row.items():
                        # Truncate long values
                        str_value = str(value)
                        if len(str_value) > 100:
                            str_value = str_value[:100] + "..."
                        print(f"  {key}: {str_value}")
            else:
                print(f"[OK] Table exists but is EMPTY")

        except Exception as e:
            error_msg = str(e)
            if "does not exist" in error_msg.lower() or "relation" in error_msg.lower():
                print(f"[ERROR] Table does NOT exist")
            else:
                print(f"[ERROR] Error querying table: {error_msg}")

    print("\n" + "="*60)
    print("Database check complete!")
    print("="*60)

except ImportError:
    print("[ERROR] Supabase package not installed. Run: pip install supabase")
except Exception as e:
    print(f"[ERROR] Error: {e}")
