import os
from google import genai

client = genai.Client()
chunks = ["Hello world", "This is a test"]

try:
    resp = client.models.embed_content(model='gemini-embedding-2', contents=chunks)
    print("Number of embeddings returned:", len(resp.embeddings))
except Exception as e:
    print("Error:", e)
