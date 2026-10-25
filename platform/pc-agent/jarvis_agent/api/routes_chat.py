"""Yazılı sohbet ucu — ortak çekirdek (chat/service.run_chat) + sesli moda geçiş.

Gereklim 5.4: yazılı modda "Jarvis sesli moda geç" algılanırsa "Tamamdır"
der ve sesli moda geçer.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..chat.service import run_chat
from ..core import counters
from ..core import screen as screen_module
from ..store import database
from ..store import section_f  # Bölüm F: XP + activity (madde 20/21)
from ..voice.textmatch import is_enter_voice_command
from .. import security

logger = logging.getLogger("jarvis.api.chat")

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@router.post("/api/chat")
async def chat(payload: ChatRequest, request: Request) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Mesaj boş olamaz.")

    counters.bump_command_count()
    voice = getattr(request.app.state, "voice", None)
    owner_id = security.request_owner(request)
    # Misafir (Madde 6): sohbet DB'ye yazılmaz, geçmiş bağlamı kullanılmaz.
    guest = security.is_guest(request)

    # ── "Jarvis sesli moda geç" — LLM'e gitmeden yerelde yakalanır ──
    if voice is not None and is_enter_voice_command(message):
        if not guest:
            database.add_message("user", message, owner_id=owner_id)
        database.audit("chat.voice_enter_command", detail=message[:200])
        if voice.status().get("mic_available"):
            if not guest:
                database.add_message("assistant", "Tamamdır.", owner_id=owner_id)
            voice.start_voice_mode(
                reason="text_command",
                response="Sesli moddayım efendim, sizi dinliyorum.",
            )
            return {
                "reply": "Tamamdır.",
                "used_tools": [],
                "provider": "local-command",
                "model": "voice-gate",
                "error": False,
                "voice_mode": True,
            }
        reply = (
            "Üzgünüm efendim, bu cihazda mikrofon bulunamadığı için sesli moda "
            "geçemiyorum."
        )
        if not guest:
            database.add_message("assistant", reply, owner_id=owner_id)
        return {
            "reply": reply,
            "used_tools": [],
            "provider": "local-command",
            "model": "voice-gate",
            "error": False,
            "voice_mode": False,
        }

    # Madde 3/1: dil ve konuşma modu sahibinin user_settings'inden gelir.
    owner_prefs = database.get_user_settings(owner_id)
    # ── Madde 27: günlük kullanım limiti — aşıldıysa sohbet 429 ile reddedilir.
    from ..store import section_g  # yerel import: daireden bağımsız kullanım

    if not guest:
        section_g.touch_usage(owner_id)
        if section_g.usage_today(owner_id).get("limit_reached"):
            raise HTTPException(
                status_code=429,
                detail="Günlük kullanım limitine ulaşıldı. Yarın tekrar deneyin.",
            )
    # ── Madde 26: kişilik (isim/stil) — prompt'u şekillendirir.
    persona_name = str(owner_prefs.get("persona_name") or "")
    persona_style = str(owner_prefs.get("persona_style") or "classic")
    # ── Madde 22: özel komutlar — eşleşirse LLM'e gitmeden yürütülür ──
    cmd = database.match_custom_command(owner_id, message)
    if cmd is not None:
        counters.bump_command_count()
        action = cmd["action_type"]
        payload_text = (cmd["action_payload"] or "").strip()
        if action == "reply_text":
            reply = payload_text or "Tamamdır."
        else:  # open_app — beyaz liste (core.screen)
            try:
                screen_module.open_app(payload_text)
                reply = f"{payload_text} açıldı."
            except ValueError:
                reply = f"'{payload_text}' beyaz listede yok; açamıyorum."
            except Exception:
                logger.exception("Özel komut: uygulama başlatılamadı")
                reply = "Uygulama başlatılırken bir sorun oluştu."
        if not guest:
            database.add_message("user", message, owner_id=owner_id)
            database.add_message("assistant", reply, owner_id=owner_id)
        database.audit("chat.custom_command", detail=f"{cmd['phrase']} -> {action}")
        return {
            "reply": reply,
            "used_tools": [],
            "provider": "custom-command",
            "model": action,
            "error": False,
        }

    result = await run_chat(
        message,
        request.app.state.llm,
        request.app.state.stats,
        source="text",
        owner_id=owner_id,
        # Madde 25 (Privacy Mode): gizli sohbet DB'ye yazılmaz (log tutulmaz).
        persist=(not guest) and not bool(owner_prefs.get("privacy_mode")),
        language=owner_prefs.get("language") or "tr",
        mode=owner_prefs.get("conversation_mode") or "adaptive",
        mood=owner_prefs.get("mood") or "neutral",
        persona_name=persona_name,
        persona_style=persona_style,
    )
    # Bölüm F (madde 21): sohbet XP'si — sunucu tarafında, misafir hariç.
    section_f.award_xp(owner_id, "chat")
    section_f.log_activity(owner_id, "chat", message[:60])
    return result
