"""Belge ayrıştırma + chunk'lama (Özellik 8.1).

Desteklenen formatlar: PDF, TXT, MD, DOCX.
- PDF: pypdf (kurulu değilse zarif hata mesajı)
- DOCX: zipfile + XML (stdlib; python-docx gerekmez)
- TXT/MD: doğrudan okuma

Chunk boyutu: ~500 token (≈2000 karakter, 4 karakter/token varsayımı),
50 token (≈200 karakter) örtüşme — mega prompt 8.1 değerleri.
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

_CHUNK_CHARS = 2000   # ≈ 500 token
_OVERLAP_CHARS = 200  # ≈ 50 token

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md", ".docx")


class ExtractionError(RuntimeError):
    """Dosya metne çevrilemedi."""


def extract_text(filename: str, data: bytes) -> str:
    """Dosya uzantısına göre metni çıkarır."""
    lowered = (filename or "").lower()
    if lowered.endswith(".pdf"):
        return _extract_pdf(data)
    if lowered.endswith(".docx"):
        return _extract_docx(data)
    if lowered.endswith((".txt", ".md")) or lowered == "":
        return data.decode("utf-8", errors="replace")
    raise ExtractionError(
        "Desteklenmeyen format (PDF, TXT, MD, DOCX kabul edilir)."
    )


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # graceful degradation
        raise ExtractionError(
            "PDF ayrıştırma için pypdf gerekli: pip install pypdf"
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages).strip()
    except Exception as exc:  # noqa: BLE001 — bozuk PDF kullanıcıya net mesaj döner
        raise ExtractionError(f"PDF okunamadı: {exc}") from exc
    if not text:
        raise ExtractionError("PDF'te metin bulunamadı (image-only olabilir).")
    return text


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml_data = zf.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ExtractionError("Geçersiz DOCX dosyası.") from exc
    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError as exc:
        raise ExtractionError("DOCX XML'i ayrıştırılamadı.") from exc
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for para in root.iter(f"{{{ns['w']}}}p"):
        runs = [
            node.text or "" for node in para.iter(f"{{{ns['w']}}}t")
        ]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _clean(text: str) -> str:
    """Başlık/cümle sınırlarını bozmadan boşlukları sıkıştırır."""
    return re.sub(r"[ \t]+", " ", text or "").strip()


def chunk_text(text: str, chunk_chars: int = _CHUNK_CHARS,
               overlap: int = _OVERLAP_CHARS) -> list[str]:
    """Metni örtüşmeli chunk'lara böler (her chunk tek bir bilgi parçası)."""
    text = _clean(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_chars - overlap)
    while start < len(text):
        piece = text[start:start + chunk_chars].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_chars >= len(text):
            break
        start += step
    return chunks[:200]  # güvenlik: tek belge için üst sınır
