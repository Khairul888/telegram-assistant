#!/usr/bin/env python3
"""
Simple endpoint testing script for Telegram Assistant.
"""

import requests
import json
import sys

def test_endpoint(url, description):
    """Test a single endpoint."""
    try:
        print(f"\n=== Testing {description} ===")
        print(f"URL: {url}")

        response = requests.get(url, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response:")

        try:
            # Try to parse as JSON
            json_response = response.json()
            print(json.dumps(json_response, indent=2))
        except:
            # If not JSON, print as text
            print(response.text[:500])

        return response.status_code == 200

    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Test all endpoints."""
    base_url = "http://localhost:8000"

    endpoints = [
        ("/", "Root endpoint"),
        ("/health", "Health check"),
        ("/status", "Status endpoint"),
        ("/docs", "API documentation"),
    ]

    print("Telegram Assistant - Endpoint Testing")
    print("=" * 50)

    success_count = 0
    total_count = len(endpoints)

    for path, description in endpoints:
        url = f"{base_url}{path}"
        if test_endpoint(url, description):
            success_count += 1

    print(f"\n=== RESULTS ===")
    print(f"Successful: {success_count}/{total_count}")
    print(f"Success Rate: {(success_count/total_count)*100:.1f}%")

    if success_count == total_count:
        print("[OK] All endpoints working!")
        sys.exit(0)
    else:
        print("[ERROR] Some endpoints failed")
        sys.exit(1)

if __name__ == "__main__":
    main()