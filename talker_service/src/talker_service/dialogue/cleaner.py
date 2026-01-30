"""Dialogue cleaner - removes unwanted content from LLM responses."""

import re
from typing import Optional


def clean_dialogue(text: str) -> str:
    """Clean up LLM-generated dialogue.
    
    Removes:
    - Quotes around speech
    - Name prefixes (e.g., "Hip: ")
    - Action descriptions in asterisks (*sighs*)
    - Bracketed emotions ([laughs])
    - Common AI artifacts
    
    Args:
        text: Raw LLM response text
        
    Returns:
        Cleaned dialogue text
    """
    if not text:
        return ""
    
    # Remove outer quotes
    text = text.strip()
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]
    
    # Remove name prefixes like "Hip: " or "[Hip]:"
    text = re.sub(r'^\[?[A-Za-z]+\]?:\s*', '', text)
    
    # Remove action descriptions in asterisks: *sighs*, *looks around*
    text = re.sub(r'\*[^*]+\*', '', text)
    
    # Remove bracketed emotions/actions: [laughs], (sighs)
    text = re.sub(r'\[[^\]]+\]', '', text)
    text = re.sub(r'\([^)]+\)', '', text)
    
    # Remove common AI artifacts
    artifacts = [
        "I cannot assist with that",
        "I'm sorry, but",
        "As an AI",
        "As a language model",
    ]
    for artifact in artifacts:
        if artifact.lower() in text.lower():
            # This is likely a refusal, return empty
            return ""
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Strip and return
    return text.strip()


def extract_speaker_id(response: str) -> Optional[str]:
    """Extract speaker ID from LLM speaker selection response.
    
    Handles various response formats:
    - JSON: {"id": 123}
    - Labeled: ID: 123 or [ID: 123]
    - Plain: 123
    
    Args:
        response: Raw LLM response
        
    Returns:
        Speaker ID as string, or None if extraction failed
    """
    if not response:
        return None
    
    # Try JSON format first
    try:
        import json
        data = json.loads(response.strip())
        if isinstance(data, dict) and "id" in data:
            return str(data["id"])
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Try labeled format: ID: 123 or [ID: 123]
    match = re.search(r'ID:\s*(\d+)', response, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Try plain number
    match = re.search(r'(\d+)', response)
    if match:
        return match.group(1)
    
    return None
