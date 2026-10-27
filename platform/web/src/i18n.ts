/**
 * i18n (madde 3) — Türkçe/İngilizce kullanıcıya görünür metinler.
 *
 * Kullanım: `import { t, setLang, getLang } from "../i18n"` → t("auth.login").
 * Dil tercihi localStorage'da önbelleklenir; oturum açıldığında DB'deki
 * user_settings.language ile senkronlanır (useJarvis bunu yapar).
 * Eksik anahtar durumunda: önce İngilizce fallback, sonra anahtarın kendisi
 * döner — böylece arayüz asla boş metin göstermez.
 */

export type Lang = "tr" | "en";

const STORAGE_KEY = "jarvis.lang";

type Dict = Record<string, string>;

const tr: Dict = {
  // Genel
  "app.title": "J.A.R.V.I.S",
  "common.save": "Kaydet",
  "common.saving": "Kaydediliyor...",
  "common.cancel": "İptal",
  "common.close": "Kapat",
  "common.refresh": "Yenile",
  "common.delete": "Sil",
  "common.online": "Çevrimiçi",
  "common.offline": "Çevrimdışı",
  "common.error": "Hata",
  "common.retry": "Tekrar dene",
  "common.loading": "Yükleniyor...",

  // TopBar
  "topbar.settings": "Ayarlar",
  "topbar.system_cards": "Sistem kartları",
  "topbar.online": "ONLINE",
  "topbar.offline": "OFFLINE",

  // Sohbet paneli
  "chat.title": "Conversation",
  "chat.clear": "Temizle",
  "chat.confirm_clear": "Emin misiniz?",
  "chat.export": "Dışa aktar",
  "chat.empty": "Konuşma boş. Bir şeyler yazın...",
  "chat.placeholder": "Jarvis'e yazın...",
  "chat.placeholder_offline": "Çevrimdışı — bağlantı bekleniyor",
  "chat.offline_note":
    "Bağlantı koptu — mesajlar kaydedilemiyor. Bağlantı gelince tekrar deneyin.",
  "chat.send": "Gönder",
  "chat.unknown_error": "Bilinmeyen hata",
  "alarm.mute": "Sustur",
  "alarm.more": "alarm daha",

  // Ayarlar
  "settings.title": "Ayarlar",
  "settings.language": "Dil",
  "settings.language_tr": "Türkçe",
  "settings.language_en": "English",
  "settings.theme": "Tema",
  "settings.chat_position": "Sohbet paneli konumu",
  "settings.chat_position_right": "Sağ",
  "settings.chat_position_center": "Orta",
  "settings.city": "Şehir",
  "settings.connection": "Bağlantı",
  "settings.llm_provider": "LLM Sağlayıcısı",
  "settings.microphone": "Mikrofon",
  "settings.save_failed": "Kaydedilemedi",
  "settings.wake_phrases": "Uyandırma İfadeleri (her satıra bir tane)",
  "settings.exit_phrases": "Sesli Mod Çıkış İfadeleri (virgülle)",
  "settings.clap": "Çift Alkış ile Uyandırma",
  "settings.clap_sensitivity": "Alkış Hassasiyeti",
  "settings.less_sensitive": "Daha az duyarlı",
  "settings.more_sensitive": "Daha duyarlı",
  "integrations.ready": "Hazır",
  "integrations.off": "Kapalı",
  "integrations.whatsapp": "WhatsApp",
  "integrations.mail": "E-posta",
  "integrations.home_assistant": "Home Assistant",
  "integrations.relay": "Relay",

  // Tema renkleri
  "theme.red": "Kırmızı",
  "theme.green": "Yeşil",
  "theme.blue": "Mavi",
  "theme.maroon": "Bordo",

  // Eşleştirme
  "pair.title": "Cihazlar",
  "pair.none": "Eşleşmiş cihaz yok. QR üreterek telefonu tanıt.",
  "pair.scan_hint": "Telefonun kamerasıyla okut",
  "pair.scan_hint_secs": "sn",
  "pair.browser_hint": "veya tarayıcıda aç:",
  "pair.start": "QR ile cihaz eşleştir",
  "pair.renew": "QR'ı yenile",
  "pair.remove_device": "Cihazı kaldır",
  "pair.start_failed": "Eşleştirme başlatılamadı",
  "pair.remove_failed": "Cihaz kaldırılamadı",
  "pair.last_seen": "son görülme",
  "pair.device": "cihaz",
  "pair.enter_pin": "PIN kodunu elle gir",
  "pair.continue_guest": "Misafir olarak devam et",

  // Kimlik doğrulama (Prompt 1)
  "auth.title": "JARVIS'e giriş",
  "auth.subtitle": "Hesabınıza giriş yapın veya yeni hesap oluşturun.",
  "auth.login": "Giriş yap",
  "auth.register": "Kayıt ol",
  "auth.forgot": "Şifremi unuttum",
  "auth.logout": "Çıkış yap",
  "auth.first_name": "Ad",
  "auth.last_name": "Soyad",
  "auth.birth_date": "Doğum tarihi (YYYY-AA-GG)",
  "auth.password": "Şifre (en az 8 karakter)",
  "auth.security_question": "Güvenlik sorusu",
  "auth.security_answer": "Güvenlik cevabı",
  "auth.new_password": "Yeni şifre",
  "auth.reset_hint": "Doğum tarihi ve güvenlik cevabınızla şifrenizi yenileyin.",
  "auth.reset_done": "Şifreniz güncellendi. Giriş yapabilirsiniz.",
  "auth.back_to_login": "Girişe dön",
  "auth.failed": "İşlem başarısız",
  "auth.rate_limited": "Çok fazla hatalı deneme. Lütfen bekleyin.",
  "auth.unavailable":
    "Sunucuda kimlik doğrulama yapılandırılmamış (JARVIS_JWT_SECRET). Yerelde giriş yapmadan devam edebilirsiniz.",
  "auth.session_expired": "Oturumunuz sona erdi, lütfen tekrar giriş yapın.",

  // Misafir modu (Prompt 2)
  "guest.banner": "Misafir modundasınız, sohbetler kaydedilmez.",
  "guest.blocked": "Misafir modunda kullanılamaz",
  "guest.exit": "Misafir modundan çık",

  // Konuşma modları (Prompt 3)
  "settings.mode": "Konuşma modu",
  "mode.formal": "Resmi",
  "mode.formal_desc": "Profesyonel, toplantı dili.",
  "mode.casual": "Arkadaş",
  "mode.casual_desc": "Samimi, espri anlayışlı.",
  "mode.adaptive": "Duruma göre",
  "mode.adaptive_desc": "Bilgi sunarken resmi, sohbette samimi.",

  // Tema (Prompt 0/4)
  "theme.light": "Açık",
  "theme.dark": "Koyu",
  "theme.custom": "Özel",
  "settings.custom_palette": "Özel palet",
  "settings.custom_accent": "Vurgu rengi",
  "settings.custom_bg": "Arka plan rengi",

  // Hava durumu (konum)
  "weather.location": "Konumumu kullan",
  "weather.location_denied": "Konum izni verilmedi; kayıtlı şehir kullanılıyor.",

  // Madde 14: TTS ses ayarları
  "settings.tts_voice": "Konuşma sesi",
  "settings.tts_rate": "Konuşma hızı",
  "settings.tts_rate_hint": "0.5x – 2.0x arası; hız değişimi için ffmpeg gerekir.",
  // Bölüm E: üretkenlik (madde 23) + hafıza (madde 18)
  "productivity.title": "Üretkenlik",
  "productivity.tab_notes": "Notlar",
  "productivity.tab_todos": "Yapılacaklar",
  "productivity.tab_memory": "Hafıza",
  "productivity.note_title": "Başlık",
  "productivity.note_content": "İçerik (isteğe bağlı)",
  "productivity.add": "Ekle",
  "productivity.empty_notes": "Not yok.",
  "productivity.empty_todos": "Yapılacak yok.",
  "productivity.empty_memory": "Kalıcı bilgi yok.",
  "productivity.memory_placeholder": "Kalıcı hatırlamamı istediğin bilgi",
  "productivity.todo_placeholder": "Yeni yapılacak",
  "productivity.guest_locked": "Misafir modunda kullanılamaz.",
  // Bölüm E (madde 9): ekran analizi
  "agent.screen_analyze": "Ekranı analiz et",
  "agent.screen_analyzing": "Analiz ediliyor...",
  "agent.screen_failed": "Ekran analizi şu an kullanılamıyor.",
  // Bölüm F (madde 19/20/21/24): dosya, medya ve sosyal
  "social.title": "Dosya, Medya ve Sosyal",
  "social.tab_xp": "Seviye",
  "social.tab_macros": "Makrolar",
  "social.tab_voice": "Sesli Not",
  "social.tab_share": "Paylaş",
  "social.tab_insights": "Analitik",
  "social.xp_total": "Toplam XP",
  "social.streak": "Günlük seri",
  "social.level_progress": "Seviye ilerlemesi",
  "social.badges": "Rozetler",
  "social.no_badges": "Henüz rozet yok.",
  "social.daily_tasks": "Günlük görevler",
  "social.leaderboard": "Liderlik tablosu",
  "social.leader_empty": "Henüz kimse puan almadı.",
  "social.macro_name": "Makro adı",
  "social.macro_add": "Makro ekle",
  "social.macro_empty": "Makro yok.",
  "social.voice_placeholder": "Sesli not metni (konuşmadan metne)",
  "social.voice_add": "Not ekle",
  "social.voice_empty": "Sesli not yok.",
  "social.voice_search": "Notlarda ara",
  "social.share_create": "Paylaşımlı oturum aç",
  "social.share_code": "Oturum kodu",
  "social.share_join": "Katıl",
  "social.share_name": "Görünen ad",
  "social.share_message": "Mesaj yaz...",
  "social.share_send": "Gönder",
  "social.share_empty": "Henüz mesaj yok.",
  "social.share_host_only": "Oturumu yalnızca açan silebilir.",
  "social.insights_days": "Son 14 gün",
  "social.export_json": "JSON indir",
  "social.export_csv": "CSV indir",
  "social.notes_export": "Notları indir (MD)",
  "social.backup_export": "Yedek al (ZIP)",
  "social.backup_import": "Yedeği geri yükle",
  "social.import_ok": "Yedek geri yüklendi",
  "social.import_failed": "Geri yükleme başarısız",
  "social.activity": "Son etkinlikler",
  "social.activity_empty": "Etkinlik yok.",
  "social.files_search": "Etiketli dosya ara",
  "social.files_empty": "Sonuç yok.",
  // __G_I18N__ — Bölüm G (madde 25/26/27): Dict düz anahtarlı olduğu için
  // iç içe nesne yerine noktalı anahtarlar kullanılır.
  "g.common.save": "Kaydet",
  "g.common.cancel": "Vazgeç",
  "g.common.delete": "Sil",
  "g.common.refresh": "Yenile",
  "g.common.loading": "Yükleniyor...",
  "g.common.error": "İşlem başarısız oldu",
  "g.common.done": "Kaydedildi",
  "g.common.passphrase": "Şifre",
  "g.common.unlock": "Kilidi aç",
  "g.common.locked": "Kilitli",
  "g.common.add": "Ekle",
  "g.common.note": "Not",
  "g.tabs.privacy": "Gizlilik",
  "g.tabs.permissions": "İzinler",
  "g.tabs.audit": "Denetim",
  "g.tabs.wellness": "Sağlık",
  "g.tabs.a11y": "Erişilebilirlik",
  "g.tabs.personality": "Kişilik",
  "g.privacy.title": "Gizlilik Kasası",
  "g.privacy.desc": "Not içerikleri tarayıcında AES-GCM ile şifrelenir; şifre sunucuya hiç gönderilmez. Şifreyi unutursan içerikler kurtarılamaz.",
  "g.privacy.mode": "Gizli sohbet modu",
  "g.privacy.mode_desc": "Gizli sohbetler kaydedilmez ve loglanmaz.",
  "g.privacy.new_title": "Not başlığı",
  "g.privacy.new_body": "Not içeriği",
  "g.privacy.reveal_hint": "İçeriği çözmek için şifreyi yukarıya gir",
  "g.privacy.decrypt_err": "Şifre hatalı veya veri bozuk",
  "g.privacy.empty": "Not yok",
  "g.privacy.open": "Aç",
  "g.permissions.title": "Hassas İşlem İzinleri",
  "g.permissions.desc": "Her hassas işlem için ayrı ayrı izin ver.",
  "g.audit.title": "Güvenlik Denetim Kaydı",
  "g.audit.empty": "Kayıt yok",
  "g.audit.download": "İndir (CSV)",
  "g.wellness.title": "Sağlık ve Odak",
  "g.wellness.mood_q": "Bugün modun nasıl?",
  "g.wellness.mood_neutral": "Nötr",
  "g.wellness.mood_focused": "Odaklı",
  "g.wellness.mood_tired": "Yorgun",
  "g.wellness.mood_stressed": "Stresli",
  "g.wellness.mood_cheerful": "Neşeli",
  "g.wellness.focus": "Odak modu",
  "g.wellness.break_min": "Mola hatırlatıcı (dk)",
  "g.wellness.daily": "Günlük kullanım limiti (dk)",
  "g.wellness.used": "Bugün kullanılan",
  "g.a11y.title": "Erişilebilirlik ve Görünüm",
  "g.a11y.font": "Yazı ölçeği",
  "g.a11y.fs_sm": "Küçük",
  "g.a11y.fs_md": "Normal",
  "g.a11y.fs_lg": "Büyük",
  "g.a11y.dyslexic": "Disleksi dostu yazı tipi",
  "g.a11y.contrast": "Yüksek kontrast",
  "g.a11y.widgets": "Panel sırası (virgülle)",
  "g.a11y.persona": "JARVIS kişiliği",
  "g.a11y.persona_hint": "örn: resmi ve kısa cevaplar",
  "privacy.tab_privacy": "Gizlilik",
  "privacy.tab_wellness": "Sağlık",
  "privacy.error": "Hata",
  "privacy.mode": "Gizlilik modu",
  "privacy.mode_desc": "Gizlilik modunda sohbetler ve loglar kaydedilmez.",
  "privacy.lock": "Şimdi kilitle",
  "privacy.permissions": "İzinler",
  "privacy.notes": "Gizli notlar",
  "privacy.note_title": "Başlık",
  "privacy.note_pass": "Parola",
  "privacy.note_content": "İçerik",
  "privacy.note_create": "Not ekle",
  "privacy.note_read": "Göster",
  "privacy.note_delete": "Sil",
  "privacy.empty": "Kayıt yok",
  "privacy.audit": "Güvenlik denetim kaydı",
  "privacy.audit_download": "İndir (JSON)",
  "wellness.mood": "Bugünkü ruh hâli",
  "wellness.focus": "Odak modu",
};

const en: Dict = {
  "app.title": "J.A.R.V.I.S",
  "common.save": "Save",
  "common.saving": "Saving...",
  "common.cancel": "Cancel",
  "common.close": "Close",
  "common.refresh": "Refresh",
  "common.delete": "Delete",
  "common.online": "Online",
  "common.offline": "Offline",
  "common.error": "Error",
  "common.retry": "Retry",
  "common.loading": "Loading...",

  "topbar.settings": "Settings",
  "topbar.system_cards": "System cards",
  "topbar.online": "ONLINE",
  "topbar.offline": "OFFLINE",

  "chat.title": "Conversation",
  "chat.clear": "Clear",
  "chat.confirm_clear": "Are you sure?",
  "chat.export": "Export",
  "chat.empty": "No messages yet. Say something...",
  "chat.placeholder": "Type to Jarvis...",
  "chat.placeholder_offline": "Offline — waiting for connection",
  "chat.offline_note":
    "Connection lost — messages cannot be saved right now. Try again once you're back online.",
  "chat.send": "Send",
  "chat.unknown_error": "Unknown error",
  "alarm.mute": "Mute",
  "alarm.more": "more alarm(s)",

  "settings.title": "Settings",
  "settings.language": "Language",
  "settings.language_tr": "Türkçe",
  "settings.language_en": "English",
  "settings.theme": "Theme",
  "settings.chat_position": "Chat panel position",
  "settings.chat_position_right": "Right",
  "settings.chat_position_center": "Center",
  "settings.city": "City",
  "settings.connection": "Connection",
  "settings.llm_provider": "LLM Provider",
  "settings.microphone": "Microphone",
  "settings.save_failed": "Could not save",
  "settings.wake_phrases": "Wake phrases (one per line)",
  "settings.exit_phrases": "Voice mode exit phrases (comma-separated)",
  "settings.clap": "Wake on double clap",
  "settings.clap_sensitivity": "Clap sensitivity",
  "settings.less_sensitive": "Less sensitive",
  "settings.more_sensitive": "More sensitive",
  "integrations.ready": "Ready",
  "integrations.off": "Off",
  "integrations.whatsapp": "WhatsApp",
  "integrations.mail": "E-mail",
  "integrations.home_assistant": "Home Assistant",
  "integrations.relay": "Relay",

  "theme.red": "Red",
  "theme.green": "Green",
  "theme.blue": "Blue",
  "theme.maroon": "Maroon",

  "pair.title": "Devices",
  "pair.none": "No paired devices. Generate a QR code to pair your phone.",
  "pair.scan_hint": "Scan with your phone camera",
  "pair.scan_hint_secs": "s",
  "pair.browser_hint": "or open in browser:",
  "pair.start": "Pair device via QR",
  "pair.renew": "Refresh QR",
  "pair.remove_device": "Remove device",
  "pair.start_failed": "Could not start pairing",
  "pair.remove_failed": "Could not remove device",
  "pair.last_seen": "last seen",
  "pair.device": "device",
  "pair.enter_pin": "Enter PIN manually",
  "pair.continue_guest": "Continue as guest",

  "auth.title": "Sign in to JARVIS",
  "auth.subtitle": "Sign in to your account or create a new one.",
  "auth.login": "Sign in",
  "auth.register": "Create account",
  "auth.forgot": "Forgot password",
  "auth.logout": "Sign out",
  "auth.first_name": "First name",
  "auth.last_name": "Last name",
  "auth.birth_date": "Birth date (YYYY-MM-DD)",
  "auth.password": "Password (min 8 chars)",
  "auth.security_question": "Security question",
  "auth.security_answer": "Security answer",
  "auth.new_password": "New password",
  "auth.reset_hint": "Reset your password with your birth date and security answer.",
  "auth.reset_done": "Password updated. You can sign in now.",
  "auth.back_to_login": "Back to sign in",
  "auth.failed": "Request failed",
  "auth.rate_limited": "Too many failed attempts. Please wait.",
  "auth.unavailable":
    "Authentication is not configured on the server (JARVIS_JWT_SECRET). You can continue locally without signing in.",
  "auth.session_expired": "Your session expired, please sign in again.",

  "guest.banner": "You are in guest mode; chats are not saved.",
  "guest.blocked": "Not available in guest mode",
  "guest.exit": "Leave guest mode",

  "settings.mode": "Conversation mode",
  "mode.formal": "Formal",
  "mode.formal_desc": "Professional, meeting language.",
  "mode.casual": "Casual",
  "mode.casual_desc": "Friendly and humorous.",
  "mode.adaptive": "Adaptive",

  // Bölüm E: productivity (item 23) + memory bank (item 18)
  "productivity.title": "Productivity",
  "productivity.tab_notes": "Notes",
  "productivity.tab_todos": "To-dos",
  "productivity.tab_memory": "Memory",
  "productivity.note_title": "Title",
  "productivity.note_content": "Content (optional)",
  "productivity.add": "Add",
  "productivity.empty_notes": "No notes.",
  "productivity.empty_todos": "No to-dos.",
  "productivity.empty_memory": "No saved memories.",
  "productivity.memory_placeholder": "Something you want me to remember",
  "productivity.todo_placeholder": "New to-do",
  "productivity.guest_locked": "Not available in guest mode.",
  // Bölüm E (item 9): screen analysis
  "agent.screen_analyze": "Analyze my screen",
  "agent.screen_analyzing": "Analyzing...",
  "agent.screen_failed": "Screen analysis is unavailable right now.",

  // Bölüm F (madde 19/20/21/24): dosya, medya ve sosyal
  "social.title": "Files, Media & Social",
  "social.tab_xp": "Level",
  "social.tab_macros": "Macros",
  "social.tab_voice": "Voice Notes",
  "social.tab_share": "Share",
  "social.tab_insights": "Analytics",
  "social.xp_total": "Total XP",
  "social.streak": "Daily streak",
  "social.level_progress": "Level progress",
  "social.badges": "Badges",
  "social.no_badges": "No badges yet.",
  "social.daily_tasks": "Daily tasks",
  "social.leaderboard": "Leaderboard",
  "social.leader_empty": "Nobody has earned points yet.",
  "social.macro_name": "Macro name",
  "social.macro_add": "Add macro",
  "social.macro_empty": "No macros.",
  "social.voice_placeholder": "Voice note text (speech-to-text)",
  "social.voice_add": "Add note",
  "social.voice_empty": "No voice notes.",
  "social.voice_search": "Search notes",
  "social.share_create": "Create shared session",
  "social.share_code": "Session code",
  "social.share_join": "Join",
  "social.share_name": "Display name",
  "social.share_message": "Type a message...",
  "social.share_send": "Send",
  "social.share_empty": "No messages yet.",
  "social.share_host_only": "Only the host can delete the session.",
  "social.insights_days": "Last 14 days",
  "social.export_json": "Download JSON",
  "social.export_csv": "Download CSV",
  "social.notes_export": "Download notes (MD)",
  "social.backup_export": "Create backup (ZIP)",
  "social.backup_import": "Restore backup",
  "social.import_ok": "Backup restored",
  "social.import_failed": "Restore failed",
  "social.activity": "Recent activity",
  "social.activity_empty": "No activity.",
  "social.files_search": "Search files by tag",
  "social.files_empty": "No results.",


  "mode.adaptive_desc": "Formal when presenting facts, casual in conversation.",

  "theme.light": "Light",
  "theme.dark": "Dark",
  "theme.custom": "Custom",
  "settings.custom_palette": "Custom palette",
  "settings.custom_accent": "Accent color",
  "settings.custom_bg": "Background color",

  "weather.location": "Use my location",
  "weather.location_denied": "Location permission denied; using saved city.",

  "settings.tts_voice": "Speech voice",
  "settings.tts_rate": "Speech rate",
  "settings.tts_rate_hint": "0.5x – 2.0x; rate change requires ffmpeg.",
  // __G_I18N__ — Section G (items 25/26/27): flat keys (Dict is Record<string,string>)
  "g.common.save": "Save",
  "g.common.cancel": "Cancel",
  "g.common.delete": "Delete",
  "g.common.refresh": "Refresh",
  "g.common.loading": "Loading...",
  "g.common.error": "Operation failed",
  "g.common.done": "Saved",
  "g.common.passphrase": "Passphrase",
  "g.common.unlock": "Unlock",
  "g.common.locked": "Locked",
  "g.common.add": "Add",
  "g.common.note": "Note",
  "g.tabs.privacy": "Privacy",
  "g.tabs.permissions": "Permissions",
  "g.tabs.audit": "Audit",
  "g.tabs.wellness": "Wellness",
  "g.tabs.a11y": "Accessibility",
  "g.tabs.personality": "Personality",
  "g.privacy.title": "Privacy Vault",
  "g.privacy.desc": "Note contents are encrypted in your browser with AES-GCM; the passphrase never leaves your device. If you forget it, contents cannot be recovered.",
  "g.privacy.mode": "Private chat mode",
  "g.privacy.mode_desc": "Private chats are not stored or logged.",
  "g.privacy.new_title": "Note title",
  "g.privacy.new_body": "Note content",
  "g.privacy.reveal_hint": "Enter the passphrase above to decrypt",
  "g.privacy.decrypt_err": "Wrong passphrase or corrupted data",
  "g.privacy.empty": "No notes yet",
  "g.privacy.open": "Open",
  "g.permissions.title": "Sensitive Action Permissions",
  "g.permissions.desc": "Grant permission per sensitive action.",
  "g.audit.title": "Security Audit Log",
  "g.audit.empty": "No entries",
  "g.audit.download": "Download (CSV)",
  "g.wellness.title": "Health & Focus",
  "g.wellness.mood_q": "How is your mood today?",
  "g.wellness.mood_neutral": "Neutral",
  "g.wellness.mood_focused": "Focused",
  "g.wellness.mood_tired": "Tired",
  "g.wellness.mood_stressed": "Stressed",
  "g.wellness.mood_cheerful": "Cheerful",
  "g.wellness.focus": "Focus mode",
  "g.wellness.break_min": "Break reminder (min)",
  "g.wellness.daily": "Daily usage limit (min)",
  "g.wellness.used": "Used today",
  "g.a11y.title": "Accessibility & Appearance",
  "g.a11y.font": "Font scale",
  "g.a11y.fs_sm": "Small",
  "g.a11y.fs_md": "Normal",
  "g.a11y.fs_lg": "Large",
  "g.a11y.dyslexic": "Dyslexia-friendly font",
  "g.a11y.contrast": "High contrast",
  "g.a11y.widgets": "Widget order (comma separated)",
  "g.a11y.persona": "JARVIS personality",
  "g.a11y.persona_hint": "e.g. formal and concise",
  "privacy.tab_privacy": "Privacy",
  "privacy.tab_wellness": "Wellness",
  "privacy.error": "Error",
  "privacy.mode": "Privacy mode",
  "privacy.mode_desc": "In privacy mode, chats and logs are not stored.",
  "privacy.lock": "Lock now",
  "privacy.permissions": "Permissions",
  "privacy.notes": "Secret notes",
  "privacy.note_title": "Title",
  "privacy.note_pass": "Passphrase",
  "privacy.note_content": "Content",
  "privacy.note_create": "Add note",
  "privacy.note_read": "Reveal",
  "privacy.note_delete": "Delete",
  "privacy.empty": "No records",
  "privacy.audit": "Security audit log",
  "privacy.audit_download": "Download (JSON)",
  "wellness.mood": "Today's mood",
  "wellness.focus": "Focus mode",
};

const DICTS: Record<Lang, Dict> = { tr, en };

let currentLang: Lang = detectInitialLang();
const missing = new Set<string>();

function detectInitialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "tr" || stored === "en") return stored;
  } catch {
    /* localStorage yok (gizli mod) — varsayılan tr */
  }
  const nav = typeof navigator !== "undefined" ? navigator.language.toLowerCase() : "tr";
  return nav.startsWith("en") ? "en" : "tr";
}

/** Şu anki dili döndürür. */
export function getLang(): Lang {
  return currentLang;
}

/** Dili değiştirir, kalıcı hale getirir ve değişiklik olayını yayınlar. */
export function setLang(lang: Lang): void {
  currentLang = lang === "en" ? "en" : "tr";
  try {
    localStorage.setItem(STORAGE_KEY, currentLang);
  } catch {
    /* kalıcı saklama yok — yalnızca oturumluk */
  }
  document.documentElement.lang = currentLang;
  window.dispatchEvent(new CustomEvent("jarvis:lang-change"));
}

/** Anahtarı aktif dilde döndürür; eksikse EN fallback, o da yoksa anahtar. */
export function t(key: string): string {
  const value = DICTS[currentLang][key] ?? DICTS.en[key];
  if (value !== undefined) return value;
  // Eksik anahtarı bir kez bildir (Faz 2 i18n testi bunu yakalar).
  if (!missing.has(key)) {
    missing.add(key);
    console.warn(`[i18n] Eksik çeviri anahtarı: "${key}"`);
  }
  return key;
}

/** i18n test yardımcısı — oturum boyunca eksik kalan anahtarlar. */
export function missingKeys(): string[] {
  return [...missing];
}

