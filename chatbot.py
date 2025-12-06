import google.generativeai as genai
import os
from dotenv import load_dotenv
# Set your Gemini API key
# It is recommended to use environment variables: os.environ["GEMINI_API_KEY"]
load_dotenv()
genai.configure(api_key=GEMINI_API_KEY)

def chatbot_response(prompt, file_path=None, mime_type=None, history=[]):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # If there's history, start a chat session
        if history:
            chat = model.start_chat(history=history)
            
            content = [prompt]
            if file_path:
                uploaded_file = genai.upload_file(file_path, mime_type=mime_type)
                content.append(uploaded_file)
                
            response = chat.send_message(content)
            return response.text.strip()
        
        # Fallback for single turn (or if history is empty)
        content = [prompt]
        if file_path:
            uploaded_file = genai.upload_file(file_path, mime_type=mime_type)
            content.append(uploaded_file)

        response = model.generate_content(content)
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"
