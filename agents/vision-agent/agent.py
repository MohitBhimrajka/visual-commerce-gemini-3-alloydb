"""
Vision Agent: Core Gemini 3 Flash logic for image analysis.
Extracted for reuse by main.py A2A server and standalone verification.
Production: Deploy main.py to Cloud Run with --port 8081.
"""
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

# Initialize Gemini client with API key (no GCP project required)
# The SDK auto-discovers GEMINI_API_KEY or GOOGLE_API_KEY from environment
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY")
)


def analyze_image(image_bytes: bytes, query: str = "Write code to count the exact number of boxes on this shelf.", mime_type: str = "image/jpeg") -> dict:
    """
    Sends the image to Gemini 3 Flash for analysis.
    With Code Execution enabled, the model writes Python (OpenCV) to count items.
    """
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[image_part, query],
        config=types.GenerateContentConfig(
            temperature=0,
            # CODELAB STEP 1: Uncomment to enable deep reasoning
            # thinking_config=types.ThinkingConfig(
            #     thinking_level=types.ThinkingLevel.HIGH  # Production: use MEDIUM to reduce cost
            # ),
            # CODELAB STEP 2: Uncomment to enable code execution
            # tools=[types.Tool(code_execution=types.ToolCodeExecution())]
        ),
    )

    result = {"plan": "", "code_output": "", "answer": ""}

    if response.candidates:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                result["answer"] += part.text
            if hasattr(part, "executable_code") and part.executable_code:
                result["plan"] = f"Generated code: {part.executable_code.code}"
            if hasattr(part, "code_execution_result") and part.code_execution_result:
                result["code_output"] = str(part.code_execution_result.output or "")

    return result


def main():
    """Run standalone verification against sample image."""
    script_dir = Path(__file__).parent
    image_path = script_dir / "assets" / "warehouse_shelf.png"
    if not image_path.exists():
        print("> Sample image not found. Run with an image path.")
        return
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    print("> Analyzing image with Gemini 3 Flash...")
    result = analyze_image(image_bytes, mime_type=mime)
    if result["plan"]:
        print(f"> Plan: {result['plan'][:80]}...")
    if result["code_output"]:
        print("> Executing generated Python code...")
        print(f"> Code output: {result['code_output']}")
    if result["answer"]:
        print(f"> Answer: {result['answer'].strip()}")
    else:
        print("> No analysis returned.")


if __name__ == "__main__":
    main()
