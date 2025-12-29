"""Test script for validating tool definitions and imports."""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)


def test_tool_imports():
    """Test that all tool definitions can be imported and are valid."""

    print("="*60)
    print("Testing Tool Definition Imports")
    print("="*60)

    tools_to_test = [
        ("expense_tools", "EXPENSE_TOOLS"),
        ("itinerary_tools", "ITINERARY_TOOLS"),
        ("places_tools", "PLACES_TOOLS"),
        ("trip_tools", "TRIP_TOOLS"),
        ("settlement_tools", "SETTLEMENT_TOOLS")
    ]

    all_passed = True

    for module_name, const_name in tools_to_test:
        try:
            # Import module
            module = __import__(f"api.agents.tools.{module_name}", fromlist=[const_name])
            tools = getattr(module, const_name)

            # Validate structure
            if not isinstance(tools, list):
                print(f"[FAIL] {module_name}: Not a list")
                all_passed = False
                continue

            # Check each tool has required fields
            for i, tool in enumerate(tools):
                if "name" not in tool:
                    print(f"[FAIL] {module_name}: Tool {i} missing 'name'")
                    all_passed = False
                if "description" not in tool:
                    print(f"[FAIL] {module_name}: Tool {i} missing 'description'")
                    all_passed = False
                if "parameters" not in tool:
                    print(f"[FAIL] {module_name}: Tool {i} missing 'parameters'")
                    all_passed = False

            print(f"[PASS] {module_name}: {len(tools)} tools defined")

        except Exception as e:
            print(f"[FAIL] {module_name}: {e}")
            all_passed = False

    print("\n" + "="*60)
    print("Testing GeminiService import and call_function method")
    print("="*60)

    try:
        from api.services.gemini_service import GeminiService

        # Check if call_function method exists
        if hasattr(GeminiService, 'call_function'):
            print("[PASS] GeminiService.call_function method exists")
        else:
            print("[FAIL] GeminiService.call_function method not found")
            all_passed = False

    except Exception as e:
        print(f"[FAIL] GeminiService import: {e}")
        all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("All tests PASSED!")
    else:
        print("Some tests FAILED")
    print("="*60)

    return all_passed


if __name__ == "__main__":
    success = test_tool_imports()
    sys.exit(0 if success else 1)
