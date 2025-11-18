# src/services/gemini_ocr.py
import base64
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

client = genai.Client(api_key=API_KEY)

def extract_text_from_image_gemini(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    b64 = base64.b64encode(image_bytes).decode()
    contents = [
        {"role":"user","parts":[{"inlineData":{"mimeType":mime_type,"data":b64}}]},
        {"role":"user","parts":[{"text":"Extract all alphanumeric text from the image. Return plain text only."}]}
    ]
    resp = client.models.generate_content(model="gemini-2.0-flash", contents=contents)
    return (resp.text or "").strip()
