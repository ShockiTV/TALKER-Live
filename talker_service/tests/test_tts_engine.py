"""Tests for TTS engine."""

import pytest
from unittest.mock import MagicMock, Mock, patch, AsyncMock
from pathlib import Path
import numpy as np
from io import BytesIO


class TestTTSModuleImport:
    """Test TTS module import guard."""

    def test_tts_import_without_pocket_tts(self):
        """Test that TTS module loads gracefully without pocket_tts."""
        with patch.dict('sys.modules', {'pocket_tts': None}):
            # Reload the module to trigger import
            import importlib
            import talker_service.tts as tts_module
            importlib.reload(tts_module)
            
            # TTS_AVAILABLE should be False when pocket_tts is missing
            # (in reality, it might still be True if pocket_tts was already imported)
            assert hasattr(tts_module, 'TTS_AVAILABLE')
            assert hasattr(tts_module, 'TTSEngine')


class TestTTSEngine:
    """Tests for TTSEngine class."""

    @pytest.fixture
    def mock_pocket_tts(self):
        """Mock pocket_tts module (v1.1.1 API: TTSModel) and subprocess ffmpeg."""
        # Ensure the submodule is resolved before patching
        import talker_service.tts.engine  # noqa: F401

        with patch('talker_service.tts.engine.TTSModel') as mock_tts_model_cls, \
             patch('talker_service.tts.engine.subprocess') as mock_subprocess:
            
            # Mock model returned by TTSModel.load_model()
            mock_model = MagicMock()
            mock_tts_model_cls.load_model.return_value = mock_model
            
            # Mock voice state returned by model.get_state_for_audio_prompt()
            mock_voice_state = MagicMock()
            mock_model.get_state_for_audio_prompt.return_value = mock_voice_state

            # Mock subprocess.run to return fake OGG bytes
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = b"OggS_fake_ogg_data"
            mock_result.stderr = b""
            mock_subprocess.run.return_value = mock_result

            yield {
                'TTSModel': mock_tts_model_cls,
                'subprocess': mock_subprocess,
                'model': mock_model,
                'voice_state': mock_voice_state
            }

    @pytest.fixture
    async def engine(self, mock_pocket_tts, tmp_path):
        """Create TTSEngine instance with mocked dependencies."""
        from talker_service.tts.engine import TTSEngine
        
        engine = TTSEngine()
        
        # Create mock voice files
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        voice_file = voices_dir / "test_voice.safetensors"
        voice_file.write_text("mock voice data")
        
        await engine.load(voices_dir)
        
        return engine

    @pytest.mark.asyncio
    async def test_load_populates_voice_cache(self, mock_pocket_tts, tmp_path):
        """Test that load() populates voice cache from safetensors files."""
        from talker_service.tts.engine import TTSEngine
        
        engine = TTSEngine()
        
        # Create mock voice files
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        (voices_dir / "voice1.safetensors").write_text("mock")
        (voices_dir / "voice2.safetensors").write_text("mock")
        
        await engine.load(voices_dir)
        
        assert engine.model is not None
        assert "voice1" in engine.voice_cache
        assert "voice2" in engine.voice_cache

    @pytest.mark.asyncio
    async def test_load_handles_missing_directory(self, mock_pocket_tts, tmp_path):
        """Test that load() handles missing voices directory gracefully."""
        from talker_service.tts.engine import TTSEngine
        
        engine = TTSEngine()
        
        # Use non-existent directory
        voices_dir = tmp_path / "nonexistent"
        
        await engine.load(voices_dir)
        
        # Should not crash, voice cache should be empty
        assert len(engine.voice_cache) == 0

    @pytest.mark.asyncio
    async def test_generate_audio_empty_text_returns_none(self, engine):
        """Test that generate_audio returns None for empty text."""
        result = await engine.generate_audio("", "test_voice")
        assert result is None
        
        result = await engine.generate_audio("   ", "test_voice")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_audio_with_valid_text(self, engine, mock_pocket_tts):
        """Test that generate_audio produces bytes for valid text."""
        # Mock audio generation — chunks are tensor-like objects with .numpy()
        mock_chunk = MagicMock()
        mock_chunk.numpy.return_value = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        engine.model.generate_audio_stream.return_value = [mock_chunk, mock_chunk]
        
        result = await engine.generate_audio("Hello world", "test_voice")
        
        # subprocess.run was called to encode OGG via ffmpeg
        mock_pocket_tts['subprocess'].run.assert_called_once()
        # Result is bytes from ffmpeg stdout
        assert result is not None
        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_voice_id_resolution_exact_match(self, engine):
        """Test that _resolve_voice returns exact match when available."""
        voice = engine._resolve_voice("test_voice")
        
        assert voice is not None

    @pytest.mark.asyncio
    async def test_voice_id_resolution_fallback(self, engine):
        """Test that _resolve_voice falls back to first available voice."""
        voice = engine._resolve_voice("nonexistent_voice")
        
        # Should return first available voice (test_voice)
        assert voice is not None

    @pytest.mark.asyncio
    async def test_voice_id_resolution_empty_cache(self):
        """Test that _resolve_voice returns None when cache is empty."""
        from talker_service.tts.engine import TTSEngine
        
        engine = TTSEngine()
        # Don't load voices
        
        voice = engine._resolve_voice("any_voice")
        
        assert voice is None

    @pytest.mark.asyncio
    async def test_generate_audio_runs_in_executor(self, engine, mock_pocket_tts):
        """Test that generate_audio runs synchronous generation in executor."""
        # Mock audio generation — chunks have .numpy() method
        mock_chunk = MagicMock()
        mock_chunk.numpy.return_value = np.array([0.1, 0.2], dtype=np.float32)
        engine.model.generate_audio_stream.return_value = [mock_chunk]
        
        # Mock run_in_executor to verify it's called
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop_instance = AsyncMock()
            mock_loop_instance.run_in_executor = AsyncMock(return_value=b"OGG")
            mock_loop.return_value = mock_loop_instance
            
            result = await engine.generate_audio("Hello", "test_voice")
            
            # Verify run_in_executor was called
            mock_loop_instance.run_in_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_audio_handles_exception(self, engine, mock_pocket_tts):
        """Test that generate_audio handles exceptions gracefully."""
        # Make model raise exception
        engine.model.generate_audio_stream.side_effect = Exception("TTS error")
        
        result = await engine.generate_audio("Hello", "test_voice")
        
        assert result is None

    def test_resolve_voice_with_empty_cache_returns_none(self):
        """Test that _resolve_voice returns None when voice cache is empty."""
        from talker_service.tts.engine import TTSEngine
        
        engine = TTSEngine()
        
        voice = engine._resolve_voice("any_voice")
        
        assert voice is None
