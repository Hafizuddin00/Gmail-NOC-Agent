"""
scripts/list_models.py
----------------------
Utility to list all Gemini models that support the generateContent action.

Run from the project root:
    python scripts/list_models.py
"""

import os
import sys

# Allow imports from the project root when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Models supporting generateContent:\n")
for model in client.models.list():
    if "generateContent" in model.supported_actions:
        print(f"  {model.name}")
