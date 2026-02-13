#!/usr/bin/env python3
"""
Standalone test script for Vision Agent.
Tests Gemini 3 Flash vision analysis without running the full system.

Usage:
    export GEMINI_API_KEY="your-api-key-here"
    python3 test_vision_agent.py path/to/image.png
"""
import sys
from pathlib import Path

# Add agents/vision-agent to path
sys.path.insert(0, str(Path(__file__).parent / "agents" / "vision-agent"))

from agent import analyze_image


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_vision_agent.py <image_path>")
        print("\nExample:")
        print("  python3 test_vision_agent.py assets/samples/warehouse_shelf_1.png")
        print("\nMake sure GEMINI_API_KEY is set in your environment or .env file")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"Testing Vision Agent with Gemini 3 Flash")
    print(f"{'='*80}")
    print(f"Image: {image_path}")
    print(f"Size: {image_path.stat().st_size / 1024:.1f} KB")
    print(f"{'='*80}\n")
    
    # Read image
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    
    # Test query (same as used in production)
    query = """Analyze this warehouse shelf image. Write code to:
1) Count the exact number of items/boxes
2) Describe the type of items (boxes, containers, parts, etc.)
3) Note any visible labels or identifying features

Format: 'Found X [item type]. [Description]'"""
    
    print(f"Query: {query}\n")
    print(f"Calling Gemini 3 Flash...\n")
    
    # Call Vision Agent
    try:
        result = analyze_image(image_bytes, query=query, mime_type=mime)
        
        print(f"{'='*80}")
        print(f"RESULT")
        print(f"{'='*80}")
        
        if result.get("plan"):
            print(f"\n📋 Plan:")
            print(f"{result['plan']}")
        
        if result.get("code_output"):
            print(f"\n🔢 Code Output:")
            print(f"{result['code_output']}")
        
        if result.get("answer"):
            print(f"\n💡 Answer:")
            print(f"{result['answer']}")
        
        print(f"\n{'='*80}")
        print(f"WHAT FRONTEND WOULD RECEIVE")
        print(f"{'='*80}")
        
        # Simulate what the agent_executor sends
        answer = result.get("answer", "No analysis returned.")
        code_output = result.get("code_output", "")
        
        if code_output:
            full_response = f"Code output: {code_output}\n\n{answer}"
        else:
            full_response = answer
        
        # Extract search terms
        import re
        search_terms = []
        numbers = re.findall(r'\d+', code_output) if code_output else []
        if numbers:
            search_terms.append(f"{numbers[0]} items")
        
        inventory_keywords = ['box', 'boxes', 'container', 'package', 'unit', 'part', 'item', 'component']
        for keyword in inventory_keywords:
            if keyword in answer.lower():
                search_terms.append(keyword)
                break
        
        if search_terms:
            search_hint = f"\n\nSearch terms: {', '.join(search_terms)}"
            full_response += search_hint
        
        print(f"\n{full_response}")
        print(f"\n{'='*80}")
        
        # Success summary
        print(f"\n✅ Test completed successfully!")
        print(f"\n📊 Summary:")
        print(f"  - Plan generated: {'Yes' if result.get('plan') else 'No'}")
        print(f"  - Code executed: {'Yes' if result.get('code_output') else 'No'}")
        print(f"  - Answer provided: {'Yes' if result.get('answer') else 'No'}")
        print(f"  - Search terms: {search_terms if search_terms else 'None extracted'}")
        print(f"  - Response length: {len(full_response)} characters")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        print(f"\nFull traceback:")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
