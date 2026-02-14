"""
Vision Agent: Core Gemini 3 Flash logic for image analysis.
Extracted for reuse by agent_executor.py (A2A server) and standalone verification.
Production: Deploy main.py to Cloud Run with --port 8081.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Gemini client with API key (no GCP project required)
# The SDK auto-discovers GEMINI_API_KEY or GOOGLE_API_KEY from environment
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY")
)

# System instruction for precision counting + spatial detection
SYSTEM_INSTRUCTION = """You are a precision inventory counting and detection agent.

Rules:
1. Identify the PRIMARY object type in the image (boxes, bottles, cans, parts, etc.)
2. Count ONLY distinct, individual physical items — do NOT double-count
3. Partially visible items at edges count ONLY if more than 50% visible
4. Write Python code to help verify your count
5. After counting, provide the 2D bounding box for EACH detected object as box_2d: [ymin, xmin, ymax, xmax] normalized to 0-1000
6. Label each object with a short unique description (position, color, size)
7. If uncertain, err on the lower count — precision over recall
8. Your final count MUST match the number of bounding boxes you provide"""

# Default query: generic, works for any object type (boxes, bottles, parts, etc.)
DEFAULT_QUERY = (
    "Analyze this image:\n"
    "1. Identify the primary object type\n"
    "2. Write and execute Python code to count all distinct objects precisely\n"
    "3. For EACH detected object, provide its bounding box as box_2d: [ymin, xmin, ymax, xmax] normalized to 0-1000\n"
    "4. Label each object with a short unique description\n\n"
    "Your final count must match the number of bounding boxes."
)


def analyze_image(image_bytes: bytes, query: str = None, mime_type: str = "image/jpeg") -> dict:
    """
    Sends the image to Gemini 3 Flash for analysis.
    With Code Execution enabled, the model writes Python code to count items
    and provides bounding box coordinates for each detected object.
    """
    if query is None:
        query = DEFAULT_QUERY

    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[image_part, query],
        config=types.GenerateContentConfig(
            system_instruction=[types.Part.from_text(text=SYSTEM_INSTRUCTION)],
            temperature=0,
            # CODELAB STEP 1: Uncomment to enable reasoning
            # thinking_config=types.ThinkingConfig(
            #    thinking_level="LOW",     # Valid: "MINIMAL", "LOW", "MEDIUM", "HIGH"
            #    include_thoughts=False    # Set to True for debugging
            #),
            # CODELAB STEP 2: Uncomment to enable code execution
            # tools=[types.Tool(code_execution=types.ToolCodeExecution)]
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
        logger.error("Sample image not found. Run with an image path.")
        return
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    logger.info("Analyzing image with Gemini 3 Flash...")
    result = analyze_image(image_bytes, mime_type=mime)
    if result["plan"]:
        logger.info(f"Plan: {result['plan'][:80]}...")
    if result["code_output"]:
        logger.info("Executing generated Python code...")
        logger.info(f"Code output: {result['code_output']}")
    if result["answer"]:
        logger.info(f"Answer: {result['answer'].strip()}")
    else:
        logger.warning("No analysis returned.")


if __name__ == "__main__":
    main()
