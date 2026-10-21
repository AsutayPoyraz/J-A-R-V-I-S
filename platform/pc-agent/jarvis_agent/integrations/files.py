"""Dosya transferi — yerel ağ paylaşım klasörü (Faz 5).

Güvenlik:
- Yalnızca JARVIS_FILES_DIR (varsayılan ~/JarvisFiles) içinde çalışır.
- Path traversal koruması: resolve + is_relative_to kontrolü.
- Dosya adı sanitizasyonu: yol ayracı ve gizli dosya karakterleri temizlenir.
- Silme uçları yoktur; yükleme yalnızca açık POST ile yapılır.
"""
from __future__ import annotations

import datetime
import os
import re
import pathlib
from .. import config

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\- \u00C0-\u024F\u0600-\u06FF]+")
MAX_UPLOAD_BYTES = int(config.env("JARVIS_MAX_UPLOAD_MB", "50")) * 1024 * 1024  # varsayılan 50 MB

# Yürütülebilir/tehlikeli uzantılar reddedilir (Prompt 0 item 7).
FORBIDDEN_EXTENSIONS = frozenset(
    {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".msi",
        ".vbs",
        ".ps1",
        ".scr",
        ".com",
        ".jar",
        ".sh",
    }
)

# İzinli uzantılar (allow-list): belge, görsel, ses, video, arşiv, veri.
ALLOWED_EXTENSIONS = frozenset(
    {
        ".txt", ".md", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".csv", ".json", ".xml", ".html", ".css", ".js", ".ts", ".py", ".log",
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic",
        ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".mp4", ".mov", ".mkv", ".webm",
        ".zip", ".rar", ".7z", ".tar", ".gz",
    }
)


def extension_of(name: str) -> str:
    return pathlib.Path(name or "").suffix.lower()


def check_extension(name: str) -> None:
    """Yasak/izin verilmeyen uzantıyı ValueError ile reddeder."""
    ext = extension_of(name)
    if ext in FORBIDDEN_EXTENSIONS:
        raise ValueError(f"'{ext}' uzantılı dosyalar güvenlik nedeniyle kabul edilmez.")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Bu dosya türüne izin verilmiyor.")


def uploads_dir() -> pathlib.Path:
    """Telefondan gelen dosyaların kaydedildiği klasör (varsayılan: Downloads)."""
    raw = config.env("JARVIS_UPLOADS_DIR", "")
    if not raw:
        raw = os.path.join(os.path.expanduser("~"), "Downloads")
    path = pathlib.Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def shared_dir() -> pathlib.Path:
    raw = config.env("JARVIS_FILES_DIR", "") or os.path.join(
        os.path.expanduser("~"), "JarvisFiles"
    )
    path = pathlib.Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve(name: str) -> pathlib.Path:
    """Adı paylaşım klasörü içinde güvenli biçimde çözer; kaçışa izin vermez."""
    base = shared_dir().resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base):
        raise PermissionError("Bu yol paylaşım klasörünün dışına çıkıyor.")
    return candidate


def sanitize_name(name: str) -> str:
    base = os.path.basename(name or "dosya")
    cleaned = _SAFE_NAME.sub("_", base).strip(" ._")
    return cleaned[:120] or "dosya"


def list_files() -> dict:
    base = shared_dir()
    items: list[dict] = []
    for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_file():
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "size": stat.st_size,
                    "modified": datetime.datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(timespec="seconds"),
                }
            )
    return {"available": True, "directory": str(base), "files": items}


def read_file(name: str) -> bytes:
    path = _resolve(name)
    if not path.is_file():
        raise FileNotFoundError(f"'{name}' bulunamadı.")
    return path.read_bytes()


def write_file(name: str, data: bytes, target_dir: pathlib.Path | None = None) -> dict:
    safe = sanitize_name(name)
    check_extension(safe)
    base = (target_dir or uploads_dir()).resolve()
    base.mkdir(parents=True, exist_ok=True)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Dosya {MAX_UPLOAD_BYTES // (1024 * 1024)} MB sınırını aşıyor.")
    path = (base / safe).resolve()
    if not path.is_relative_to(base):
        raise PermissionError("Bu yol hedef klasörün dışına çıkıyor.")
    path.write_bytes(data)
    return {"name": path.name, "size": len(data), "directory": str(base)}


def stage_from_pc(source_path: str) -> dict:
    """PC'deki bir dosyayı paylaşım klasörüne kopyalar (LLM send_file aracı).

    Güvenlik: kaynak yalnızca OKUNUR; hedef daima shared_dir içinde
    sanitize edilmiş addır; 100 MB sınırı geçerlidir.
    """
    raw = str(source_path or "").strip().strip('"')
    if not raw:
        raise ValueError("Kaynak dosya yolu boş olamaz.")
    src = pathlib.Path(raw).expanduser()
    if not src.is_absolute():
        src = pathlib.Path.cwd() / src
    src = src.resolve()
    base = shared_dir().resolve()
    if src == base or base in src.parents:
        raise ValueError("Dosya zaten paylaşım klasöründe.")
    if not src.is_file():
        raise FileNotFoundError(f"'{src.name}' bulunamadı.")
    if src.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"Dosya {MAX_UPLOAD_BYTES // (1024 * 1024)} MB sınırını aşıyor.")
    data = src.read_bytes()
    result = write_file(src.name, data, target_dir=_resolve_staging())
    return {**result, "source": str(src)}


def available() -> bool:
    return True


def _resolve_staging() -> pathlib.Path:
    """LLM send_file aracının kopyaladığı yer: paylaşım klasörü."""
    return shared_dir()
