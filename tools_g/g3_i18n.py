# -*- coding: utf-8 -*-
"""G3: insert Section G i18n keys into tr/en blocks of i18n.ts (idempotent)."""
import io, re, glob, os, sys

R = ([p for p in glob.glob("F:/Software/JARV*") if os.path.isdir(p) and os.path.exists(p + "/platform")] or [""])[0]
P = R + "/platform/web/src/i18n.ts"
try:
    src = io.open(P, encoding="utf-8-sig").read()
except Exception as e:
    print("G3: FAIL read", e); sys.exit(0)
if "__G_I18N__" in src:
    print("G3: SKIP (already applied)"); sys.exit(0)

TR = """  // __G_I18N__
  g: {
    common: { save: "Kaydet", cancel: "Vazgeç", delete: "Sil", refresh: "Yenile", loading: "Yükleniyor...", error: "İşlem başarısız oldu", done: "Kaydedildi", passphrase: "Şifre", unlock: "Kilidi aç", locked: "Kilitli", add: "Ekle", note: "Not" },
    tabs: { privacy: "Gizlilik", permissions: "İzinler", audit: "Denetim", wellness: "Sağlık", a11y: "Erişilebilirlik", personality: "Kişilik" },
    privacy: { title: "Gizlilik Kasası", desc: "Not içerikleri tarayıcında AES-GCM ile şifrelenir; şifre sunucuya hiç gönderilmez. Şifreyi unutursan içerikler kurtarılamaz.", mode: "Gizli sohbet modu", mode_desc: "Gizli sohbetler kaydedilmez ve loglanmaz.", new_title: "Not başlığı", new_body: "Not içeriği", reveal_hint: "İçeriği çözmek için şifreyi yukarıya gir", decrypt_err: "Şifre hatalı veya veri bozuk", empty: "Not yok", open: "Aç" },
    permissions: { title: "Hassas İşlem İzinleri", desc: "Her hassas işlem için ayrı ayrı izin ver." },
    audit: { title: "Güvenlik Denetim Kaydı", empty: "Kayıt yok", download: "İndir (JSON)" },
    wellness: { title: "Sağlık ve Odak", mood_q: "Bugün modun nasıl?", mood_1: "Harika", mood_2: "İyi", mood_3: "İdare eder", mood_4: "Moralim bozuk", mood_5: "Kötü", focus: "Odak modu", break_min: "Mola hatırlatıcı (dk)", daily: "Günlük mesaj limiti", used: "Bugün kullanılan" },
    a11y: { title: "Erişilebilirlik ve Görünüm", font: "Yazı boyutu", fs_sm: "Küçük", fs_md: "Normal", fs_lg: "Büyük", dyslexic: "Disleksi dostu yazı tipi", contrast: "Yüksek kontrast", widgets: "Panel sırası (virgülle)", persona: "JARVIS kişiliği", persona_hint: "örn: resmi ve kısa cevaplar" },
  },
"""
EN = """  // __G_I18N__
  g: {
    common: { save: "Save", cancel: "Cancel", delete: "Delete", refresh: "Refresh", loading: "Loading...", error: "Operation failed", done: "Saved", passphrase: "Passphrase", unlock: "Unlock", locked: "Locked", add: "Add", note: "Note" },
    tabs: { privacy: "Privacy", permissions: "Permissions", audit: "Audit", wellness: "Wellness", a11y: "Accessibility", personality: "Personality" },
    privacy: { title: "Privacy Vault", desc: "Note contents are encrypted in your browser with AES-GCM; the passphrase never leaves your device. If you forget it, contents cannot be recovered.", mode: "Private chat mode", mode_desc: "Private chats are not stored or logged.", new_title: "Note title", new_body: "Note content", reveal_hint: "Enter the passphrase above to decrypt", decrypt_err: "Wrong passphrase or corrupted data", empty: "No notes yet", open: "Open" },
    permissions: { title: "Sensitive Action Permissions", desc: "Grant permission per sensitive action." },
    audit: { title: "Security Audit Log", empty: "No entries", download: "Download (JSON)" },
    wellness: { title: "Health & Focus", mood_q: "How is your mood today?", mood_1: "Great", mood_2: "Good", mood_3: "Okay", mood_4: "Low", mood_5: "Bad", focus: "Focus mode", break_min: "Break reminder (min)", daily: "Daily message limit", used: "Used today" },
    a11y: { title: "Accessibility & Appearance", font: "Font size", fs_sm: "Small", fs_md: "Normal", fs_lg: "Large", dyslexic: "Dyslexia-friendly font", contrast: "High contrast", widgets: "Widget order (comma separated)", persona: "JARVIS personality", persona_hint: "e.g. formal and concise" },
  },
"""

def insert(srcx, varname, text):
    m = re.search(r'(?:export\s+)?const\s+' + varname + r'\b[^=\n]*=\s*\{', srcx)
    if not m: return srcx, "NOBLOCK:" + varname
    i = m.end(); depth = 1; j = i; instr = None
    while j < len(srcx) and depth > 0:
        ch = srcx[j]
        if instr:
            if ch == "\\": j += 2; continue
            if ch == instr: instr = None
        else:
            if ch in "\"'`": instr = ch
            elif ch == "{": depth += 1
            elif ch == "}": depth -= 1
        j += 1
    if depth != 0: return srcx, "UNBALANCED:" + varname
    ls = srcx.rfind("\n", 0, j - 1) + 1
    return srcx[:ls] + text + srcx[ls:], "OK:" + varname

out, s1 = insert(src, "tr", TR)
if s1.startswith("NOBLOCK"):
    out, s1 = insert(src, "translations", TR)
out, s2 = insert(out, "en", EN)
if s2.startswith("NOBLOCK"):
    out, s2 = insert(out, "enUS", EN)
    if s2.startswith("NOBLOCK"): out, s2 = insert(out, "en_us", EN)
io.open(P, "w", encoding="utf-8", newline="\n").write(out)
print("G3:", s1, "|", s2)