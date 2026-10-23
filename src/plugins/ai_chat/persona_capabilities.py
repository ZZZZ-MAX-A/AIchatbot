"""Current persona capability choices; no clients, services or persistence."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaVoiceRoute:
    voice: str
    emotion: str
    source: str
    supported: bool
    enabled: bool
    trim_trailing_noise: bool = False


def resolve_persona_voice_route(config, scope) -> PersonaVoiceRoute:
    if scope.configuration_error:
        return PersonaVoiceRoute("", "", "unavailable", False, False)
    if not scope.routing_v2_active:
        return PersonaVoiceRoute(
            config.tts_voice, config.tts_emotion, "TTS_*", True,
            bool(config.enable_tts),
        )
    if scope.role_card_key != "linyin":
        return PersonaVoiceRoute("", "", "unavailable", False, False)
    voice, emotion = config.linyin_tts_voice, config.linyin_tts_emotion
    return PersonaVoiceRoute(
        voice, emotion, "LINYIN_TTS_*", True,
        bool(config.enable_tts and config.enable_linyin_tts and voice and emotion),
        trim_trailing_noise=True,
    )
