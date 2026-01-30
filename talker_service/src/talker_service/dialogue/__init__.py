"""Dialogue generation module for TALKER Expanded."""

from .generator import DialogueGenerator
from .speaker import SpeakerSelector

__all__ = [
    "DialogueGenerator",
    "SpeakerSelector",
]
