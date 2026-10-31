"""WebSocket uçları — canlı istatistik akışı."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import security
from ..store import database
from .routes_system import build_stats_payload

logger = logging.getLogger("jarvis.api.ws")

router = APIRouter()

PUSH_INTERVAL_SECONDS = 2.0


@dataclass
class _Connection:
    client_id: str
    websocket: WebSocket


class ConnectionManager:
    """Tracks isolated sockets; targeted sends never broadcast globally.

    Prompt 9 (ayar senkronu): aynı sahibin (owner) tüm cihazlarına yayın
    yapabilmek için her bağlantı owner ve user_id ile etiketlenir.
    """

    def __init__(self) -> None:
        self._connections: dict[str, _Connection] = {}
        self._meta: dict[str, dict[str, str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        owner: str = "",
        user_id: str = "",
    ) -> None:
        await websocket.accept()
        self._connections[client_id] = _Connection(client_id, websocket)
        self._meta[client_id] = {"owner": owner, "user_id": user_id}

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        self._meta.pop(client_id, None)

    async def send_personal_message(self, client_id: str, payload: Any) -> None:
        connection = self._connections.get(client_id)
        if connection is not None:
            await connection.websocket.send_json(payload)

    async def publish_to_owner(self, owner: str, payload: Any) -> int:
        """Aynı sahibin (user:<id> veya device:<id>) açık soketlerine yayın."""
        if not owner:
            return 0
        sent = 0
        for client_id, connection in list(self._connections.items()):
            meta = self._meta.get(client_id, {})
            if meta.get("owner") == owner:
                try:
                    await connection.websocket.send_json(payload)
                    sent += 1
                except Exception:  # kopmuş soket — yok say
                    self.disconnect(client_id)
        return sent

    async def publish_to_user(self, user_id: str, payload: Any) -> int:
        """Kullanıcının tüm cihazlarına yayın (eşleşmiş telefonlar dahil)."""
        if not user_id:
            return 0
        sent = 0
        for client_id, connection in list(self._connections.items()):
            if self._meta.get(client_id, {}).get("user_id") == user_id:
                try:
                    await connection.websocket.send_json(payload)
                    sent += 1
                except Exception:
                    self.disconnect(client_id)
        return sent

    async def broadcast_all(self, payload: Any) -> int:
        """Tüm açık soketlere yayın (kamera kurulum ilerlemesi vb.)."""
        sent = 0
        for client_id, connection in list(self._connections.items()):
            try:
                await connection.websocket.send_json(payload)
                sent += 1
            except Exception:
                self.disconnect(client_id)
        return sent


manager = ConnectionManager()


@router.websocket("/ws/stats")
async def ws_stats(websocket: WebSocket) -> None:
    """İstemciye 2 saniyede bir sistem istatistiği iter.

    İstemci koparsa sessizce sonlanır; frontend kendi tarafında yeniden
    bağlanma zamanlayıcısını yönetir (otomatik retry gereksinimi).
    Güvenlik (Faz 2): eşleştirme şartsa loopback dışı istemciler geçerli
    ``?token=`` (device_token) göndermek zorundadır.
    """
    host = websocket.client.host if websocket.client else ""
    if security.required() and not security.is_loopback(host):
        token = websocket.query_params.get("token", "")
        device = security.verify_token(token)
        if device is None:
            await websocket.close(code=4401)
            return
        websocket.state.device = device
    _owner, client_id = security.websocket_owner(websocket)
    # Prompt 1: Bearer token soket sahibini "user:<id>" yapar (eşleşmiş
    # telefonlar birden çok cihazdan aynı kullanıcıya bağlanabilir).
    state = getattr(websocket, "state", None)
    token = websocket.query_params.get("access_token", "")
    if token:
        try:
            from .. import auth

            token = auth.bearer_of(websocket) or token
            claims = auth.decode_token(token, expected_type="access")
            user_row = database.get_user_by_id(str(claims.get("sub") or ""))
            if user_row:
                state.user = user_row
        except Exception:  # geçersiz token → kimliksiz (misafir) akış
            pass
    owner_label = security.request_owner(websocket)
    user = getattr(state, "user", None) or {}
    await manager.connect(
        websocket, client_id, owner=owner_label, user_id=str(user.get("id") or "")
    )
    # Prompt 2: misafire yalnızca sohbet olayları — istatistik karesi gönderilmez
    # (sistem bilgisi sızıntısı olmasın). Sohbet olayları client_id'ye hedefli gider.
    if security.is_guest(websocket):
        try:
            await manager.send_personal_message(
                client_id, {"type": "guest", "message": "Misafir oturum: yalnızca sohbet."}
            )
            while True:
                await asyncio.sleep(PUSH_INTERVAL_SECONDS)
        except (WebSocketDisconnect, Exception):
            manager.disconnect(client_id)
        return
    try:
        while True:
            payload = build_stats_payload(websocket.app)
            payload["client_id"] = client_id
            await manager.send_personal_message(client_id, payload)
            await asyncio.sleep(PUSH_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception:  # beklenmedik kopma — uygulama düşmemeli
        manager.disconnect(client_id)
        try:
            await websocket.close()
        except Exception:
            pass


# ── Bölüm F (madde 20): paylaşılan oturum canlı sohbet kanalı ────────────────

# code -> {client_id: WebSocket}; oda bazlı yayın için ayrı kayıt
_shared_rooms: dict[str, dict[str, WebSocket]] = {}


async def _broadcast_shared(code: str, payload: dict) -> None:
    """Odada herkese yayın; kopmuş soketleri sessizce ayıklar."""
    room = _shared_rooms.get(code, {})
    for cid, sock in list(room.items()):
        try:
            await sock.send_json(payload)
        except Exception:
            room.pop(cid, None)


@router.websocket("/ws/shared/{code}")
async def ws_shared(websocket: WebSocket, code: str) -> None:
    """Paylaşılan oturumun canlı mesaj akışı (WebSocket ile ortak sohbet).

    Yetkilendirme: bağlanan istemci oturumun üyesi olmalı (owner bazlı),
    aksi halde 4403 ile kapatılır. Mesaj DB'ye yazılır ve odaya yayınlanır;
    WS kullanamayan istemciler /api/shared/.../messages uzun yoklamasını
    kullanmaya devam edebilir.
    """
    from ..store import section_f  # yerel import: döngüsel riski önle

    # Kimlik çözümü: access_token varsa kullanıcı, yoksa cihaz sahibi
    token = websocket.query_params.get("access_token", "")
    if token:
        try:
            from .. import auth

            token = auth.bearer_of(websocket) or token
            claims = auth.decode_token(token, expected_type="access")
            user_row = database.get_user_by_id(str(claims.get("sub") or ""))
            if user_row:
                websocket.state.user = user_row
        except Exception:  # geçersiz token → cihaz kimliğiyle devam
            pass
    owner = security.request_owner(websocket)
    room_code = code.upper()
    if room_code not in section_f.shared_member_codes(owner):
        logger.warning("Shared WS reddedildi: %s üye değil (%s)", owner, room_code)
        await websocket.close(code=4403)
        return
    client_id = f"sh-{room_code}-{id(websocket)}"
    await websocket.accept()
    _shared_rooms.setdefault(room_code, {})[client_id] = websocket
    try:
        # Bağlanınca son 50 mesajı gönder (sohbet bağlamı)
        history = section_f.list_shared_messages(room_code, limit=50)
        await websocket.send_json({"type": "shared.history", "messages": history})
        while True:
            data = await websocket.receive_json()
            content = str(data.get("content") or "").strip()
            if not content:
                continue
            display = str(data.get("display_name") or "guest")[:40]
            mid = section_f.add_shared_message(room_code, owner, display, "user", content)
            await _broadcast_shared(
                room_code,
                {
                    "type": "shared.message",
                    "message": {
                        "id": mid,
                        "owner_id": owner,
                        "display_name": display,
                        "role": "user",
                        "content": content,
                    },
                },
            )
    except WebSocketDisconnect:
        pass
    except Exception:  # beklenmedik kopma — oda kaydını temizle
        logger.exception("Shared WS hatası (%s)", room_code)
    finally:
        _shared_rooms.get(room_code, {}).pop(client_id, None)
