import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

print(f"Testing API Key with model: gemini-2.5-flash")

try:
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content("Hello, are you working?")
    print("\nSuccess! Response from Gemini:")
    print(response.text)
except Exception as e:
    print("\nError Details:")
    print(e)
