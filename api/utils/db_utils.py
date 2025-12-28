"""Database utilities for Supabase connection."""
import os

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


def get_supabase_client() -> 'Client':
    """
    Get Supabase client instance.

    Returns:
        Client: Configured Supabase client

    Raises:
        RuntimeError: If Supabase credentials are missing
    """
    if not SUPABASE_AVAILABLE:
        raise RuntimeError("Supabase package not installed")

    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

    return create_client(url, key)
