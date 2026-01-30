"""Speaker selection with cooldown tracking."""

import time
from typing import Any

from loguru import logger


# Default cooldown: 3 seconds in milliseconds
DEFAULT_COOLDOWN_MS = 3 * 1000


class SpeakerSelector:
    """Manages speaker selection with cooldown tracking.
    
    Tracks when speakers last spoke to prevent rapid-fire dialogue.
    """
    
    def __init__(self, cooldown_ms: int = DEFAULT_COOLDOWN_MS):
        """Initialize speaker selector.
        
        Args:
            cooldown_ms: Cooldown duration in milliseconds
        """
        self.cooldown_ms = cooldown_ms
        self._last_spoke: dict[str, int] = {}  # speaker_id -> game_time_ms
    
    def is_on_cooldown(self, speaker_id: str, current_game_time_ms: int) -> bool:
        """Check if a speaker is on cooldown.
        
        Args:
            speaker_id: Character game ID
            current_game_time_ms: Current game time in milliseconds
            
        Returns:
            True if speaker is on cooldown, False otherwise
        """
        last_time = self._last_spoke.get(speaker_id)
        if last_time is None:
            return False
        
        elapsed = current_game_time_ms - last_time
        on_cooldown = elapsed < self.cooldown_ms
        
        if on_cooldown:
            logger.debug(f"Speaker {speaker_id} on cooldown ({elapsed}ms / {self.cooldown_ms}ms)")
        
        return on_cooldown
    
    def set_spoke(self, speaker_id: str, game_time_ms: int) -> None:
        """Mark that a speaker has spoken.
        
        Args:
            speaker_id: Character game ID
            game_time_ms: Game time when they spoke
        """
        self._last_spoke[speaker_id] = game_time_ms
        logger.debug(f"Set cooldown for speaker {speaker_id} at {game_time_ms}")
    
    def get_last_spoke_time(self, speaker_id: str) -> int | None:
        """Get when a speaker last spoke.
        
        Args:
            speaker_id: Character game ID
            
        Returns:
            Game time in milliseconds, or None if never spoke
        """
        return self._last_spoke.get(speaker_id)
    
    def clear_cooldown(self, speaker_id: str) -> None:
        """Clear cooldown for a specific speaker.
        
        Args:
            speaker_id: Character game ID
        """
        self._last_spoke.pop(speaker_id, None)
    
    def clear_all_cooldowns(self) -> None:
        """Clear all speaker cooldowns."""
        self._last_spoke.clear()
    
    def filter_by_cooldown(
        self,
        speakers: list[dict[str, Any]],
        current_game_time_ms: int
    ) -> list[dict[str, Any]]:
        """Filter out speakers that are on cooldown.
        
        Args:
            speakers: List of speaker dicts with 'game_id' field
            current_game_time_ms: Current game time in milliseconds
            
        Returns:
            List of speakers not on cooldown
        """
        available = []
        for speaker in speakers:
            speaker_id = str(speaker.get("game_id", ""))
            if not self.is_on_cooldown(speaker_id, current_game_time_ms):
                available.append(speaker)
            else:
                logger.debug(f"Filtered out speaker {speaker_id} (cooldown)")
        
        return available
