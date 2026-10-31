"""Merkezî sistem promptu + olgu doğrulama sınıflandırıcısı (Özellik 1).

Tüm sistem promptu metinleri TEK yerden yönetilir (mega prompt gereksinimi):
``chat/service.py`` yalnızca buradan tüketir. ``fact_check_needed`` ise
marka/model/tarih/isim gibi olgusal soruları sohbetten ayırır; yalnız bu
sorular için web doğrulaması (llm.websearch) çalışır.

Kapatma: .env -> JARVIS_FACT_CHECK=0 (tüm doğrulama kapalı).
"""
from __future__ import annotations

import re
from typing import Optional

# ── Temel kimlik (Özellik 1: IQ 200-250 ansiklopedik doğruluk) ───────────────
BASE_TR = (
    "Sen J.A.R.V.I.S adını taşıyan kişisel bir asistansın. "
    "IQ 200-250 seviyesinde, ansiklopedik doğrulukta bir uzman olarak davran: "
    "her iddianı kendi içinde çapraz kontrol et, emin olmadığın bilgiyi tahmin "
    "etme; marka, model, tarih, isim ve sayısal olgularda hatayı sıfıra "
    "indirmeye çalış. Kullanıcınla doğal, saygılı ve akıcı Türkçe konuş; "
    "gerektiğinde 'efendim' gibi kibar bir üslup kullanabilirsin. Yanıtlarını "
    "kısa ve öz tut. Sistem saati, hava durumu ve bilgisayar durumu gibi "
    "bilgilere yalnızca sana verilen araçlar (get_system_stats, "
    "get_current_time, get_weather) aracılığıyla erişebilirsin; bu bilgileri "
    "asla tahmin etme. Olgu gerektiren sorularda web_search aracıyla "
    "doğrulama yapabilirsin. Kullanıcı dosya silme, bilgisayarı kapatma gibi "
    "yıkıcı bir işlem isterse onay olmadan yapamayacağını açıkça belirt; "
    "shell komutu çalıştırma yetkin yoktur."
)
BASE_EN = (
    "You are a personal assistant named J.A.R.V.I.S. "
    "Act as an expert with IQ 200-250 and encyclopedic accuracy: cross-check "
    "every claim internally, never guess facts you are unsure about, and "
    "drive factual error to zero for brands, models, dates, names and "
    "numbers. Speak naturally, respectfully and fluently in English. Keep "
    "answers short and to the point. You can only access system clock, "
    "weather and computer status through the given tools (get_system_stats, "
    "get_current_time, get_weather) — never guess such facts. For factual "
    "questions you may verify with the web_search tool. If the user asks for "
    "a destructive action (deleting files, shutting down the computer), "
    "clearly state that you cannot do it without confirmation; you have no "
    "shell access."
)

# Geriye dönük uyumluluk: eski içe aktarmalar (chat.service, testler) bu isimleri
# kullanır. Değerler yukarıdaki temel promptlara aynen bağlanır.
SYSTEM_PROMPT_TR = BASE_TR
SYSTEM_PROMPT_EN = BASE_EN
SYSTEM_PROMPT = SYSTEM_PROMPT_TR


# ── Üslup ekleri (madde 1/26/27) ─────────────────────────────────────────────
MODE_TONE_TR = {
    "formal": (
        "Üslup: resmî ve profesyonel — yönetim kurulu sunumu gibi ölçülü, "
        "saygılı ve net konuş; şakaya girmeden bilgiyi aktar."
    ),
    "casual": (
        "Üslup: samimi bir arkadaş gibi — esprili, rahat ve sıcak konuş; "
        "'efendim' gibi resmî hitaplardan kaçın, hafif espri yapabilirsin."
    ),
    "adaptive": (
        "Üslup: duruma göre uyum sağla — araştırma/bilgi aktarımında resmî "
        "ve net ol; kullanıcı şaka yaptığında samimi ve esprili ol; yeniden "
        "soru sorulduğunda resmî tona dön."
    ),
}
MODE_TONE_EN = {
    "formal": (
        "Tone: formal and professional — measured, respectful and clear, "
        "like a board-room briefing; convey information without jokes."
    ),
    "casual": (
        "Tone: casual like a close friend — relaxed, warm and playful; "
        "avoid formal honorifics, light humor is welcome."
    ),
    "adaptive": (
        "Tone: adaptive to context — formal and precise for research and "
        "factual answers, friendly and playful when the user jokes, and "
        "back to formal when a serious question follows."
    ),
}

STYLE_HINT_TR = {
    "friendly": " Ekstra sıcak ve samimi bir ton kullan.",
    "concise": " Son derece kısa yanıt ver; gereksiz söz kullanma.",
    "funny": " Uygun olduğunda hafif ve zarif espri ekle.",
}
STYLE_HINT_EN = {
    "friendly": " Keep an extra warm, friendly tone.",
    "concise": " Be extra concise; answer in as few words as possible.",
    "funny": " Add light, tasteful humor when appropriate.",
}

MOOD_HINT_TR = {
    "focused": " Kullanıcı odaklanmış: kısa, doğrudan ve madde madde yanıt ver.",
    "tired": " Kullanıcı yorgun: sade anlat, uzun listelerden kaçın.",
    "stressed": " Kullanıcı stresli: sakin ve kısa bir ton kullan.",
    "cheerful": " Kullanıcı neşeli: enerjik ve pozitif bir ton sergile.",
    "neutral": "",
}
MOOD_HINT_EN = {
    "focused": " The user is focused: be brief, direct and bullet-pointed.",
    "tired": " The user is tired: keep it light, avoid long lists.",
    "stressed": " The user is stressed: use a calm, reassuring tone.",
    "cheerful": " The user is cheerful: mirror an upbeat, positive tone.",
    "neutral": "",
}


def build_system_prompt(
    language: str = "tr",
    mode: str = "adaptive",
    mood: str = "neutral",
    persona_name: str = "",
    persona_style: str = "classic",
) -> str:
    """Dil, üslup modu, ruh hâli ve kişilik tercihlerini prompta işler."""
    from .. import config  # dairesel içe aktarmayı önler

    lang = language if language in config.ALLOWED_LANGUAGES else "tr"
    if mode not in config.ALLOWED_CONVERSATION_MODES:
        mode = config.DEFAULT_CONVERSATION_MODE
    base = BASE_EN if lang == "en" else BASE_TR
    tones = MODE_TONE_EN if lang == "en" else MODE_TONE_TR
    prompt = f"{base} {tones.get(mode, tones['adaptive'])}"
    name = (persona_name or "").strip()[:40]
    if name:
        if lang == "en":
            prompt += f' Address the user as "{name}".'
        else:
            prompt += f' Kullanıcıya "{name}" diye hitap et.'
    styles = STYLE_HINT_EN if lang == "en" else STYLE_HINT_TR
    prompt += styles.get(persona_style or "classic", "")
    moods = MOOD_HINT_EN if lang == "en" else MOOD_HINT_TR
    return prompt + moods.get(mood, "")


# ── Olgu doğrulama sınıflandırıcısı (Özellik 1.5) ────────────────────────────
# Selamlama / yaratıcı yazı / basit eylem istekleri doğrulamadan muaf tutulur.
_SKIP_PATTERNS = (
    "merhaba", "selam", "günaydın", "iyi geceler", "iyi akşamlar", "naber",
    "nasılsın", "teşekkür", "sağol", "hello", "hi ", "hey ", "thanks",
    "şiir", "şarkı", "hikaye", "masal", "fıkra", "espri", "şaka", "yaz bana",
    "bana bir", "poem", "story", "joke", "sing", "write me",
)

_FACT_PATTERNS = (
    r"hangi", r"hangisi", r"kim(dir)?\b", r"ne zaman", r"kaç\b",
    r"nerede", r"hangi ülke", r"hangi marka", r"hangi şehir", r"hangi yıl",
    r"kaç yaşında", r"kaç para", r"kim icat", r"kim kurdu",
    r"yılında", r"doğum tarihi", r"kuruluş", r"nüfusu", r"başkenti",
    r"nedir", r"kimdir", r"kaçıncı",
    r"\bwho\b", r"\bwhen\b", r"\bwhich\b", r"\bwhere\b", r"\bwhat year\b",
    r"\bhow many\b", r"\bhow old\b", r"\bwho invented\b", r"\bcapital of\b",
)
_FACT_RE = re.compile("|".join(_FACT_PATTERNS), re.IGNORECASE)

# Doğrulama anlamlı olmayan yardımcı/eylem soruları (zaten araçla çözülür)
_SKIP_FACT_RE = re.compile(
    r"saat kaç|hava durumu|hatırlat|alarm|\baç\b|kapat\b|sistem|ram|cpu|mikrofon|müzik",
    re.IGNORECASE,
)


def fact_check_needed(query: str) -> bool:
    """Soru olgu içeriyor mu? (True → web doğrulaması çalışır).

    Heuristik: selamlama/yaratıcı istekler hariç, marka/model/tarih/isim/
    sayı kalıpları varsa True. Amaç hızlı (regex) ve deterministik olmasıdır;
    LLM'e sormadan tetikleme kararını verir.
    """
    text = (query or "").strip().lower()
    if not text or len(text) < 4:
        return False
    if any(p in text for p in _SKIP_PATTERNS):
        return False
    if _SKIP_FACT_RE.search(text):
        return False
    return bool(_FACT_RE.search(text))


def build_fact_check_prompt(question: str, draft_answer: str, sources_block: str) -> str:
    """Web doğrulama turu için kullanıcı-rolü mesajı üretir."""
    return (
        "Görev: aşağıdaki taslak cevabı, verilen web arama kaynaklarına göre "
        "doğrula.\n\n"
        f"Kullanıcının sorusu: {question}\n\n"
        f"Taslak cevap: {draft_answer}\n\n"
        f"Web kaynakları (başlık — özet):\n{sources_block}\n\n"
        "Kurallar:\n"
        "1. Taslak kaynaklarla çelişiyorsa kaynağa dayanan kısa doğru cevabı yaz.\n"
        "2. Taslak doğruysa onu olduğu gibi, küçük düzeltmelerle döndür.\n"
        "3. Kaynaklar konuyla ilgisizse taslağı değiştirme.\n"
        "4. Yalnızca nihai cevabı yaz; açıklama, başlık veya alıntı ekleme."
    )


def sources_block(results: list, limit: Optional[int] = 3) -> str:
    """Arama sonuçlarını doğrulama promptu için metin bloğuna çevirir."""
    lines = []
    for item in (results or [])[: limit or 3]:
        title = str(item.get("title") or "").strip()[:120]
        snippet = str(item.get("snippet") or "").strip()[:300]
        url = str(item.get("url") or "").strip()[:200]
        lines.append(f"- {title} — {snippet} (kaynak: {url})")
    return "\n".join(lines) if lines else "(kaynak bulunamadı)"
