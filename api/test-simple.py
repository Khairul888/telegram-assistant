"""
Ultra-simple test function for Vercel to verify handler discovery.
"""

def handler(event, context):
    """Simple handler function."""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': '{"status": "ok", "message": "Simple handler works!"}'
    }