"""Bölüm F (madde 19/21/24): oyunlaştırma, analitik, sesli notlar, etiketler, yedek."""
from __future__ import annotations

import io
import json
import logging
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from .. import security
from ..integrations import files as files_mod
from ..store import section_f
from .guards import require_not_guest


def files_list_files() -> list[dict]:
    """Madde 30 deposundaki dosyalar (paylaşılan klasör, owner-scope yok)."""
    return files_mod.list_files().get("files", [])


def files_read_bytes(name: str) -> bytes:
    return files_mod.read_file(name)


log = logging.getLogger("jarvis.productivity")

router = APIRouter(prefix="/api", tags=["productivity"])


def _ctx(request: Request) -> dict:
    """Owner'ı çözer; misafir isteği 403 ile reddedilir (madde 6)."""
    require_not_guest(request)
    return {"owner_id": security.request_owner(request)}


# ── Madde 21: oyunlaştırma ───────────────────────────────────────────────────
# Not: GET /api/gamify routes_social.py içinde tek noktadan sunulur (merged).

@router.get("/gamify/leaderboard")
def gamify_leaderboard():
    """Opsiyonel sıralama — yalnızca kayıtlı kullanıcılar, isim görünen ad."""
    return {"leaders": section_f.leaderboard()}

# ── Madde 19: sesli notlar ───────────────────────────────────────────────────
# Not: /api/voice-notes uçları routes_social.py içinde tek noktadan sunulur.

# ── Madde 19: dosya etiketleri (madde 30 kurallarına tabi dosya listesi) ─────

class TagsBody(BaseModel):
    tags: list[str] = []


# Not: GET /api/files/tags routes_social.py içinde; burada yalnızca PUT var.

@router.put("/files/tags/{file_name}")
def set_file_tags(file_name: str, body: TagsBody, ctx: dict = Depends(_ctx)):
    """Dosyaya etiket ata (arama/raporlarda kullanılır)."""
    section_f.set_file_tags(ctx["owner_id"], file_name, body.tags)
    return {"ok": True}


# ── Madde 24: analitik ve raporlar ───────────────────────────────────────────
# Not: GET /api/analytics/summary routes_social.py içinde tek noktadan sunulur.

@router.get("/history/search")
def history_search(
    q: str = "",
    tag: str = "",
    date_from: str = "",
    date_to: str = "",
    ctx: dict = Depends(_ctx),
):
    """Etiketli + tarih aralıklı birleşik geçmiş arama (madde 24)."""
    return {
        "results": section_f.history_search(
            ctx["owner_id"], q=q, tag=tag, date_from=date_from, date_to=date_to
        )
    }


@router.get("/analytics/export")
def analytics_export(format: str = "json", days: int = 30, ctx: dict = Depends(_ctx)):
    """JSON/CSV veri dışa aktarma (madde 24)."""
    summary = section_f.analytics_summary(ctx["owner_id"], max(1, min(days, 365)))
    if format == "csv":
        # CSV: gun,basina_etkinlik_sayilari
        keys = sorted({k for d in summary["days"] for k in d if k != "date"})
        header = "date," + ",".join(keys)
        lines = []
        for d in summary["days"]:
            lines.append(d["date"] + "," + ",".join(str(d.get(k, 0)) for k in keys))
        csv_text = header + "\n" + "\n".join(lines)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=jarvis-analytics.csv"},
        )
    return Response(
        content=json.dumps(summary, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=jarvis-analytics.json"},
    )

# ── Madde 19: Cloud Backup MVP (JSON + dosyalar zip'i) ───────────────────────

@router.get("/backup/export")
def backup_export(ctx: dict = Depends(_ctx)):
    """Tüm owner verisini zip olarak indir: backup.json + data/ altında dosyalar."""
    data = section_f.export_owner_data(ctx["owner_id"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("backup.json", json.dumps(data, ensure_ascii=False, indent=2))
        # Yüklenen dosyalar (madde 30 deposu) da yedeğe eklenir
        for item in files_list_files():
            try:
                zf.writestr(f"data/{item['name']}", files_read_bytes(item["name"]))
            except (OSError, PermissionError, FileNotFoundError):
                continue  # dosya araya girip silindiyse yedek yine tam olsun
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=jarvis-backup.zip"},
    )


class BackupImportBody(BaseModel):
    data: dict


@router.post("/backup/import")
def backup_import(body: BackupImportBody, ctx: dict = Depends(_ctx)):
    """Yedek JSON'unu geri yükle (mevcut kayıtlara ekler)."""
    counts = section_f.import_owner_data(ctx["owner_id"], body.data)
    return {"imported": counts}

# __TAIL__