import requests
import logging
import base64

# The proxy URL for chat completions
PROXY_URL = "http://127.0.0.1:8000/v1/chat/completions"
PROXY_API_KEY = "VerysecretKey"

def transcribe_audio_file(audio_path: str, prompt: str, lang: str = "en", out_path: str | None = None) -> str:
    """
    Transcribe audio using the proxy by sending it to the chat completions endpoint.
    """
    try:
        # Language mapping for more descriptive prompts
        lang_map = {
            "en": "English", "ru": "Russian", "es": "Spanish", "fr": "French",
            "de": "German", "it": "Italian", "pt": "Portuguese", "pl": "Polish",
            "uk": "Ukrainian", "zh": "Chinese",
        }
        language_name = lang_map.get(lang, lang)

        # Dynamically construct the prompt
        instruction = f"Transcribe the following audio. The language is {language_name}."
        if prompt:
            instruction += f" For context, here is a hint about the content: '{prompt}'."
        instruction += " Return only the transcribed text, without any additional comments or formatting."

        # 1. Read audio file and encode it in base64
        with open(audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
            logging.info(f"Read {len(audio_bytes)} bytes from {audio_path}")
            encoded_data = base64.b64encode(audio_bytes).decode("utf-8")
            logging.info(f"Base64 encoded data length: {len(encoded_data)}")

        # 2. Prepare the request payload
        headers = {
            "Authorization": f"Bearer {PROXY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gemini/gemini-2.5-flash-lite-preview-06-17", # Using a model capable of audio input
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {
                            "type": "file",
                            "file": {
                                "file_data": f"data:audio/ogg;base64,{encoded_data}"
                            }
                        }
                    ]
                }
            ],
            "thinking": {"type": "enabled", "budget_tokens": -1}
        }

        # 3. Send the request
        response = requests.post(PROXY_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        # 4. Extract the transcription from the response
        response_json = response.json()
        transcription = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        print(f"Transcription from Gemini: {transcription}")
        
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(transcription)
        
        return transcription
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error transcribing audio with Gemini proxy: {e}")
        if e.response:
            logging.error(f"Response body: {e.response.text}")
        return ""
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return ""

def load_openai_api_key():
    """
    This function is a placeholder to maintain compatibility with the existing main script.
    No API key loading is needed when using the proxy.
    """
    print("Using proxy for transcription. No API key needed.")
    pass
