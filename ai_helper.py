import os
import json
import requests

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def get_api_key():
    # Attempt to read from environment variables
    return os.environ.get("GEMINI_API_KEY", "")

def call_gemini(system_instruction, prompt):
    api_key = get_api_key()
    if not api_key:
        return "[Error: GEMINI_API_KEY is not set. Please set it in your environment or Admin panel to enable AI features.]"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": system_instruction}
            ]
        }
    }
    
    try:
        response = requests.post(f"{GEMINI_API_URL}?key={api_key}", headers=headers, json=data, timeout=15)
        response.raise_for_status()
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"[Failed to connect to Gemini API: {str(e)}]"

def generate_ai_chat_response(form_data, chat_history, new_message):
    """
    Simulates a smart onboarding agent that reviews user answers and asks clarifying questions.
    """
    system_instruction = (
        "You are an expert AI web agency onboarding assistant. Your job is to interact with a client "
        "who wants a website built. Review their current questionnaire data and chat history, "
        "and help them refine their requirements (e.g. styling reference, pages, section details, logo, content). "
        "Be friendly, professional, and clear. Suggest options if they are unsure. Ask only 1-2 focused questions at a time."
    )
    
    context = f"Client Form Data:\n{json.dumps(form_data, indent=2)}\n\n"
    context += "Chat History:\n"
    for msg in chat_history:
        context += f"{msg['sender'].capitalize()}: {msg['message']}\n"
    context += f"Client: {new_message}\n"
    
    prompt = f"{context}\nGenerate the next AI response to continue clarifying the client's web requirements."
    return call_gemini(system_instruction, prompt)

def generate_developer_prompt(form_data, chat_history):
    """
    Compiles all form details and chat history into a structured Markdown Developer Prompt.
    """
    system_instruction = (
        "You are a Senior Project Manager at a manual+AI web agency. Your task is to compile all user-provided "
        "information and chat requirements into a highly detailed, structured, copy-pasteable markdown specification "
        "and developer prompt. This prompt will be used by a developer to build the website (HTML/Tailwind/JS or visual builders). "
        "Include sections for Navigation, Hero, Content, Styling, Reference sites, and an explicit list of components/pages needed."
    )
    
    context = f"Client Form Data:\n{json.dumps(form_data, indent=2)}\n\n"
    context += "Chat History:\n"
    for msg in chat_history:
        context += f"{msg['sender'].capitalize()}: {msg['message']}\n"
        
    prompt = f"{context}\nCompile a comprehensive Developer Prompt in markdown format."
    return call_gemini(system_instruction, prompt)
