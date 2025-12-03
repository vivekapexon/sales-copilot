"""
Test script to verify which agent is being loaded
"""

import sys
import os

# Add Strategy-Agent to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Strategy-Agent'))

print("=" * 60)
print("AGENT IMPORT TEST")
print("=" * 60)
print()

# Test 1: Try importing strands
print("Test 1: Importing strands library...")
try:
    import strands
    print("✓ SUCCESS: strands library imported")
    print(f"  Location: {strands.__file__}")
except ImportError as e:
    print(f"✗ FAILED: {e}")
    print("  This is why the real agent can't load")
print()

# Test 2: Try importing strategy_agent
print("Test 2: Importing strategy_agent...")
try:
    from strategy_agent import run_strategy_agent
    print("✓ SUCCESS: strategy_agent imported")
    print("  The REAL agent will be used")
    
    # Test 3: Try running it
    print()
    print("Test 3: Testing strategy agent with sample query...")
    try:
        result = run_strategy_agent("Give me the profile for HCP H123")
        print("✓ SUCCESS: Agent executed")
        print(f"  Response type: {type(result)}")
        if isinstance(result, dict) and 'Agent' in result:
            print(f"  Agent name: {result['Agent']}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        
except ImportError as e:
    print(f"✗ FAILED: {e}")
    print("  The MOCK agent will be used instead")
    print()
    
    # Test 4: Try importing mock agent
    print("Test 4: Importing mock_strategy_agent...")
    try:
        from mock_strategy_agent import run_strategy_agent
        print("✓ SUCCESS: mock_strategy_agent imported")
        print("  The MOCK agent will be used")
    except ImportError as e2:
        print(f"✗ FAILED: {e2}")
        print("  No agent available!")

print()
print("=" * 60)
print("CONCLUSION")
print("=" * 60)

# Check which agent is being used
try:
    from strategy_agent import run_strategy_agent
    print("✓ Your Streamlit app will use the REAL Strategy Agent")
except ImportError:
    try:
        from mock_strategy_agent import run_strategy_agent
        print("⚠ Your Streamlit app will use the MOCK Agent")
        print()
        print("To use the real agent:")
        print("1. Install Visual C++ Redistributable:")
        print("   https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print("2. Restart your computer")
        print("3. Run: pip install strands --no-cache-dir")
    except ImportError:
        print("✗ No agent available - app will not work")

print("=" * 60)
