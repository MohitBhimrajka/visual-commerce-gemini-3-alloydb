"""
Vision Agent: Core Gemini 3 Flash logic for image analysis.
Extracted for reuse by main.py A2A server and standalone verification.
Production: Deploy main.py to Cloud Run with --port 8081.
"""
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file (searches up directory tree)
load_dotenv(find_dotenv(usecwd=True))

# Initialize Gemini client with API key (no GCP project required)
# The SDK auto-discovers GEMINI_API_KEY or GOOGLE_API_KEY from environment
api_key = os.environ.get("GEMINI_API_KEY")
logger.info(f"Initializing Gemini client with API key: {api_key[:10] if api_key else 'NONE'}...")

client = genai.Client(
    api_key=api_key
)
logger.info("Gemini client initialized successfully")


def analyze_image(image_bytes: bytes, query: str = "Write code to count the exact number of boxes on this shelf.", mime_type: str = "image/jpeg") -> dict:
    """
    Sends the image to Gemini 3 Flash for analysis.
    With Code Execution enabled, the model writes Python (OpenCV) to count items.
    """
    logger.info("=" * 80)
    logger.info("ANALYZE_IMAGE CALLED")
    logger.info(f"Image size: {len(image_bytes)} bytes")
    logger.info(f"Mime type: {mime_type}")
    logger.info(f"Query: {query[:100]}...")
    logger.info("=" * 80)
    
    try:
        logger.info("Creating image part from bytes...")
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        logger.info("Image part created successfully")
        
        logger.info("Creating text part from query...")
        text_part = types.Part.from_text(text=query)
        logger.info("Text part created successfully")
        
        contents = [
            types.Content(
                role="user",
                parts=[image_part, text_part],
            ),
        ]
        logger.info("Contents array created")

        logger.info("Calling Gemini API with model: gemini-3-flash-preview")
        logger.info("Config: temperature=0, thinking_level=HIGH, code_execution=enabled")
        
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0,
                # CODELAB STEP 1: Uncomment to enable deep reasoning
                thinking_config=types.ThinkingConfig(
                    thinking_level="HIGH",  # Valid: "MINIMAL", "LOW", "MEDIUM", "HIGH". Use "MEDIUM" in production
                    include_thoughts=True  # Include thought summaries for debugging
                ),
                # CODELAB STEP 2: Uncomment to enable code execution
                tools=[types.Tool(code_execution=types.ToolCodeExecution)]
            ),
        )
        
        logger.info("Gemini API response received")
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Response has candidates: {hasattr(response, 'candidates') and bool(response.candidates)}")
    
    except Exception as e:
        logger.error("=" * 80)
        logger.error("GEMINI API ERROR")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Full traceback:", exc_info=True)
        logger.error("=" * 80)
        raise

    result = {"plan": "", "code_output": "", "answer": ""}

    if response.candidates:
        logger.info(f"Processing {len(response.candidates)} candidate(s)...")
        candidate = response.candidates[0]
        logger.info(f"Candidate has {len(candidate.content.parts)} part(s)")
        
        for i, part in enumerate(candidate.content.parts):
            logger.info(f"Processing part {i+1}:")
            logger.info(f"  - has text: {hasattr(part, 'text') and bool(part.text)}")
            logger.info(f"  - has executable_code: {hasattr(part, 'executable_code') and bool(part.executable_code)}")
            logger.info(f"  - has code_execution_result: {hasattr(part, 'code_execution_result') and bool(part.code_execution_result)}")
            
            if hasattr(part, "text") and part.text:
                result["answer"] += part.text
                logger.info(f"  - Added text to answer ({len(part.text)} chars)")
            if hasattr(part, "executable_code") and part.executable_code:
                result["plan"] = f"Generated code: {part.executable_code.code}"
                logger.info(f"  - Added executable code to plan ({len(part.executable_code.code)} chars)")
            if hasattr(part, "code_execution_result") and part.code_execution_result:
                result["code_output"] = str(part.code_execution_result.output or "")
                logger.info(f"  - Added code execution result ({len(result['code_output'])} chars)")
    else:
        logger.warning("No candidates in response")

    logger.info("Result summary:")
    logger.info(f"  - plan: {len(result['plan'])} chars")
    logger.info(f"  - code_output: {len(result['code_output'])} chars")
    logger.info(f"  - answer: {len(result['answer'])} chars")
    logger.info("=" * 80)
    
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
