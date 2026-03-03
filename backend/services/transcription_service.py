"""
Voice Transcription Service — Powered by AssemblyAI
Handles audio upload, transcription, and result retrieval.
"""
import assemblyai as aai
from ..config import ASSEMBLYAI_API_KEY

# ── Configure AssemblyAI ──
aai.settings.api_key = ASSEMBLYAI_API_KEY


class TranscriptionService:
    """AssemblyAI-backed transcription for voice interviews."""

    @staticmethod
    def transcribe_file(file_path: str) -> dict:
        """Transcribe an audio file using AssemblyAI."""
        try:
            config = aai.TranscriptionConfig(
                speech_model=aai.SpeechModel.best,
                sentiment_analysis=True,
                auto_highlights=True,
                language_detection=True,
            )
            transcriber = aai.Transcriber(config=config)
            transcript = transcriber.transcribe(file_path)

            if transcript.status == aai.TranscriptStatus.error:
                return {"error": transcript.error, "text": ""}

            # Extract sentiment results
            sentiments = []
            if transcript.sentiment_analysis:
                for result in transcript.sentiment_analysis:
                    sentiments.append({
                        "text": result.text,
                        "sentiment": result.sentiment.value,
                        "confidence": result.confidence,
                        "start": result.start,
                        "end": result.end,
                    })

            # Extract auto-highlights
            highlights = []
            if transcript.auto_highlights and transcript.auto_highlights.results:
                for h in transcript.auto_highlights.results:
                    highlights.append({
                        "text": h.text,
                        "count": h.count,
                        "rank": h.rank,
                    })

            return {
                "text": transcript.text or "",
                "confidence": transcript.confidence,
                "duration_ms": transcript.audio_duration,
                "word_count": len((transcript.text or "").split()),
                "sentiments": sentiments[:10],
                "highlights": highlights[:10],
                "language": transcript.language_code,
            }

        except Exception as e:
            print(f"[AssemblyAI Error] {e}")
            return {"error": str(e), "text": ""}

    @staticmethod
    def transcribe_url(audio_url: str) -> dict:
        """Transcribe audio from a URL using AssemblyAI."""
        try:
            config = aai.TranscriptionConfig(
                speech_model=aai.SpeechModel.best,
                sentiment_analysis=True,
                auto_highlights=True,
            )
            transcriber = aai.Transcriber(config=config)
            transcript = transcriber.transcribe(audio_url)

            if transcript.status == aai.TranscriptStatus.error:
                return {"error": transcript.error, "text": ""}

            return {
                "text": transcript.text or "",
                "confidence": transcript.confidence,
                "duration_ms": transcript.audio_duration,
                "word_count": len((transcript.text or "").split()),
            }
        except Exception as e:
            print(f"[AssemblyAI Error] {e}")
            return {"error": str(e), "text": ""}
