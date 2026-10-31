"""Özellik 4 — Niyet algılama: somut GÖREV/EYLEM talebi mi, bilgi sorusu mu?

Kural tabanlı (LLM'siz, milisaniyeler içinde) Türkçe sınıflandırıcı.
Amaç: kullanıcı eylem talep ettiğinde ATLAS'ı otomatik açmak; sadece merak
sorusu sorulduğunda (ör. "ATLAS ne işe yarar?") ATLAS'ı AÇMAMAK.

Sıra (öncelik yüksekten düşüğe):
1. İstek kalıbı ("günceller misin", "yapabilir misin") veya 2. tekil emir
   kipi sözcüğü ("güncelle", "aç", "çöz") ya da "atlasla ..." öneki → ACTION.
2. Soru işaretcisi (cümle içi ne/nasıl/neden/kim/hangi ... veya "mi/mı") → QUESTION.
3. Bilgisayar-işlem anahtar kelimeleri (tıkla, klavyeye yaz, uygulama aç ...) → ACTION.
4. Diğer → NEUTRAL (selam, teşekkür; ATLAS açılmaz).

Test tablosu: tests/test_intent_detection.py içinde ≥10 pozitif / ≥10 negatif.
"""
from __future__ import annotations

import re
from enum import Enum


class Intent(str, Enum):
    """Sınıflandırma sonucu."""

    ACTION = "action"      # somut görev/eylem → ATLAS açılabilir
    QUESTION = "question"  # bilgi/merak sorusu → ATLAS AÇILMAZ
    NEUTRAL = "neutral"    # selam, teşekkür vb. → ATLAS açılmaz


_TR_FOLD = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "â": "a", "î": "i", "û": "u", "İ": "i",
})

# 2. tekil emir kipi (normalize edilmiş biçimleri — Türkçe küçük/i sorunu çözüldü)
IMPERATIVE_VERBS = frozenset({
    "ac", "kapat", "calistir", "bas", "baslat", "durdur", "yenile", "kur",
    "sil", "tara", "bul", "gonder", "goster", "yaz", "tikla", "oynat",
    "degistir", "guncelle", "yukle", "indir", "coz", "hallet", "onayla",
    "bekle", "temizle", "cal", "yap", "optimize", "onar", "tamir",
})

# Soru işaretcileri (cümlede herhangi bir yerde geçmeleri yeterli)
QUESTION_WORDS = frozenset({
    "ne", "nedir", "neler", "nelerdir", "nasil", "neden", "niye", "kim",
    "kimdir", "kimin", "kimler", "hangi", "kac", "kacta", "nere", "nereye",
    "nerede", "nereden", "kacinci", "mi",
})

# İstek kalıbı: fiil gövdesi + "misin/misiniz" (kibar emir → ACTION)
_REQUEST_RE = re.compile(
    r"\b(?:yap|et|ac|kapat|calistir|coz|sil|kur|yenile|tikla|yaz|baslat|"
    r"yukle|indir|temizle|hallet|guncelle|bas|durdur|onar|tamir)"
    r"\w*\s+misiniz?\b"
)

# Mevcut atlas_intent anahtar kelimeleriyle uyumlu (jarvis_v11._send ile aynı)
COMPUTER_OP_KEYWORDS = (
    "acik pencer", "aktif pencere", "ekran", "tikla", "klavyeye",
    "uygulama ac", "program ac", "ayarleri ac", "process", "islemleri analiz",
    "dosya duzenle", "web sitesi", "site ac", "url ac", "sayfasinda",
    "yemeksepeti", "yemek sepeti", "sahibinden", "chrome", "microsoft edge",
    "edge", "google'da", "youtube'da", "fareyi", "mouse", "muzik",
    "youtube'dan", "youtube dan",
)

_ATLAS_ACTION_RE = re.compile(
    r"\b(?:"
    r"(?:chrome|google chrome|edge|microsoft edge|tarayici|uygulama|program|"
    r"site|url|ayarlar|ayarlari|sahibinden|yemeksepeti)\s+"
    r"(?:(?:u|i|yi|yu|da|de)\s+)?"
    r"(?:ac|kapat|baslat|calistir|ara|gir|oynat|indir|yenile)|"
    r"(?:google da|youtube da|youtube dan)\s+.+\s+(?:ara|oynat|cal)|"
    r"(?:klavyeye|aktif pencereye)\s+.+\s+yaz|"
    r"(?:acik pencereleri|aktif pencereyi|ekrani|fareyi|mouse u|"
    r"dosyayi|dosya)\s+.+\s+(?:goster|incele|analiz et|tikla|duzenle|"
    r"tasit|kapat|yaz|tasi)|"
    r"(?:ekran goruntusu al|islemleri analiz et)|"
    r"(?:tikla\s+\d+\s*[, ]\s*\d+|\d+\s*[, ]\s*\d+\s+tikla)|"
    r"muzik\s+(?:.+\s+)?(?:cal|oynat|ara)|"
    r"atlas(?:\s+i|i)?\s+ac"
    r")\b"
)


def _normalize(text: str) -> str:
    """Küçük harfe çevir, Türkçe harfleri sadeleştir, noktalama/boşluk temizle."""
    t = (text or "").lower()
    t = t.replace("\u0307", "")  # İ → i̇ birleşik noktası
    t = t.translate(_TR_FOLD)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def requires_atlas(text: str) -> bool:
    """Return true only for explicit computer/browser operations.

    General imperatives such as "espri yap" are actions for the assistant,
    not a reason to switch the user into the Atlas desktop-control mode.
    """
    normalized = _normalize(text)
    return bool(normalized and _ATLAS_ACTION_RE.search(normalized))


def classify_intent(text: str) -> Intent:
    """Metni ACTION / QUESTION / NEUTRAL olarak sınıflandır.

    False-positive'leri azaltmak için ACTION, QUESTION'dan önce kontrol edilir;
    ancak emir kalıbı yoksa soru işaretcisi her zaman kazanır (merak soruları
    ATLAS'ı açmaz).
    """
    t = _normalize(text)
    if not t:
        return Intent.NEUTRAL
    tokens = t.split()

    # 1) Eylem: kibar istek / emir kipi / "atlasla ..." öneki
    if _REQUEST_RE.search(t):
        return Intent.ACTION
    if any(tok in IMPERATIVE_VERBS for tok in tokens):
        return Intent.ACTION
    if tokens[0] in {"atlasla", "atlas"} and (
            len(tokens) > 1 and tokens[1] == "ile"):
        return Intent.ACTION
    if t.startswith("atlasla "):
        return Intent.ACTION

    # 2) Soru: soru işaretcisi varsa (emir yoksa) bilgi sorusudur
    if any(tok in QUESTION_WORDS for tok in tokens):
        return Intent.QUESTION

    # 3) Bilgisayar-işlem anahtar kelimeleri (mevcut atlas_intent ile uyumlu)
    if any(k in t for k in COMPUTER_OP_KEYWORDS):
        return Intent.ACTION

    return Intent.NEUTRAL
