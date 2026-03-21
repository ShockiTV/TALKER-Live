"""Compaction prompt generation for memory tier compression."""


def build_compaction_prompt(
    character_id: str,
    source_tier: str,
    source_texts: list[str],
) -> str:
    """Build LLM prompt for compacting memory tier items.
    
    Args:
        character_id: Character ID (for context)
        source_tier: Source tier name (events, summaries, digests, cores)
        source_texts: List of text items to compress
    
    Returns:
        System prompt for LLM compression
    """
    # Get tier-specific instructions
    if source_tier == "events":
        tier_instruction = (
            "You are compressing raw event records into a narrative summary. "
            "Extract the key facts, actions, and outcomes. "
            "Focus on what happened, who was involved, and consequences."
        )
        output_type = "summary"
    elif source_tier == "summaries":
        tier_instruction = (
            "You are merging multiple event summaries into a single digest. "
            "Combine related events and preserve important details. "
            "Create a coherent narrative flow."
        )
        output_type = "digest"
    elif source_tier == "digests":
        tier_instruction = (
            "You are compressing digests into a core memory. "
            "Extract the most significant events and patterns. "
            "Preserve only the most important information."
        )
        output_type = "core memory"
    else:  # cores
        tier_instruction = (
            "You are compressing core memories into a single core memory. "
            "Preserve only the most critical experiences and character-defining moments. "
            "This is the highest level of compression."
        )
        output_type = "core memory"
    
    # Build the full input text
    if len(source_texts) == 1:
        input_text = source_texts[0]
    else:
        # Number each item for clarity
        numbered_items = [
            f"{i+1}. {text}" 
            for i, text in enumerate(source_texts)
        ]
        input_text = "\n\n".join(numbered_items)
    
    # Build the prompt
    prompt = f"""You are a memory compression system. {tier_instruction}

CRITICAL RULES:
- Write in third person perspective (use "they", "their", never "I" or "my")
- Preserve chronological order when possible
- Output ONLY the compressed {output_type} text, no commentary
- Keep the output concise but preserve key details
- Use present tense for immediate events, past tense for historical context

Character ID: {character_id}

INPUT TO COMPRESS:
{input_text}

Your compressed {output_type}:"""
    
    return prompt
