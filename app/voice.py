"""
Voice: transcribe incoming voice (Whisper) and optional TTS for replies.
Enables "talk" to the superintendent: send voice message → transcribe → run graph → reply (text or voice).
"""
import io
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_bytes: bytes, filename_hint: str = "voice.ogg") -> Optional[str]:
    """
    Transcribe audio to text using OpenAI Whisper.
    Requires OPENAI_API_KEY. Accepts OGG, MP3, WAV, etc.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; cannot transcribe voice")
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        file = io.BytesIO(audio_bytes)
        file.name = filename_hint
        resp = await client.audio.transcriptions.create(
            model="whisper-1",
            file=file,
        )
        text = (resp.text or "").strip()
        return text if text else None
    except Exception as e:
        logger.warning("Whisper transcription failed: %s", e)
        return None


async def text_to_speech(text: str) -> Optional[bytes]:
    """
    Convert text to speech (OGG) using OpenAI TTS for voice replies.
    Requires OPENAI_API_KEY. Returns OGG bytes suitable for sendVoice.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not text:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        resp = await client.audio.speech.create(
            model=os.getenv("TTS_MODEL", "tts-1"),
            voice=os.getenv("TTS_VOICE", "alloy"),
            input=text[:4096],
        )
        return resp.content
    except Exception as e:
        logger.warning("TTS failed: %s", e)
        return None
