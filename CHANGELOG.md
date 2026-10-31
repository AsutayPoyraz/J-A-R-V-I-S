# Changelog
# Changelog

## [11.0.0] — 2026-10-28

JARVIS v11 "Apex+" — mega prompt'taki 19 özelliğin platform (pc-agent + web) tarafına uygulanması.

### Eklenen

- **Özellik 1 — Yüksek IQ Modu:** `llm/system_prompt.py` merkezî sistem promptu (IQ 200-250 ansiklopedik doğruluk kimliği), `web_search` aracı (DuckDuckGo varsayılan / SerpAPI, `JARVIS_SEARCH_PROVIDER`), `fact_check_needed` olgu sınıflandırıcısı ve sohbette otomatik web doğrulaması ("Web'den doğruladım:" notu).
- **Özellik 2 — İstemci Cihaz İstatistikleri:** `useClientStats.ts` hook'u (3 sn'de bir UA/deviceMemory/hardwareConcurrency/heap/batarya/ağ/ekran) + SystemStatsCard "Sunucu | Bu Cihaz" sekmeleri ve cihaz ikonu.
- **Özellik 3 — Kamera Güvenli Başlatma:** OpenCV yokluğunda `/api/camera/status` (opencv_installed/camera_available/disabled_by_env/error) + `/api/camera/install` (WS ilerlemeli pip kurulumu, `JARVIS_CAMERA_AUTO_INSTALL`) + frontend kurulum modalı.
- **Özellik 4 — Eşleştirme Sağlamlaştırma:** Çok arayüzlü LAN IP taraması (loopback/link-local hariç), `/api/pair/debug` tanı ucu, LAN origin'lere CORS.
- **Özellik 5 — Kullanıcı + API Anahtarları:** Kullanıcı adı bazlı kayıt/giriş (`/api/auth/register`, `/api/auth/login` geriye dönük uyumlu), `user_api_keys` tablosu (Fernet AES-128-CBC+HMAC — `JARVIS_MASTER_KEY`), `/api/user/api-keys` CRUD + gerçek API testi, ApiKeysSettings arayüzü, DB > .env > mock anahtar önceliği.
- **Özellik 6 — Görev Yöneticisi:** projects/tasks/subtasks tabloları, `/api/tasks/*` CRUD, `create_task/list_tasks/complete_task` LLM araçları, Kanban TaskManagerCard.
- **Özellik 7 — Ekran Özeti:** `getDisplayMedia` onaylı ekran bağlamı, `/api/screen/analyze` vision analizi, WS öneri push'u, `JARVIS_SCREEN_ANALYSIS_DISABLED`.
- **Özellik 8 — Kişisel Bilgi Tabanı (RAG):** `knowledge/` modülü (chunk + embedding + SQLite cosine retriever), `/api/knowledge/*` uçları, sohbete otomatik bağlam, KnowledgeCard.
- **Özellik 9 — Sesli Komut Makroları:** macros tablosu, `/api/macros/*`, tetikleyici ifade eşleştirmesi (textmatch), MacrosCard builder.
- **Özellik 10 — Alışkanlık Takipçisi:** habits/habit_logs/productivity_sessions tabloları, streak + ısı haritası, AI içgörüler, `/api/habits/*`.
- **Özellik 11 — Günlük Özet:** `core/daily_summary.py` (21:00 zamanlayıcı), WhatsApp/sohbet dağıtımı, `/api/summary/generate|history`, ayar toggle'ı.
- **Özellik 12 — LLM Karşılaştırma:** `/api/chat/compare` (asyncio.gather, yalnız yapılandırılmış sağlayıcılar), CompareMode yan yana kartlar, "Bu yanıtı seç".
- **Özellik 13 — trim() Düzeltmesi:** Pydantic null-safe trim validasyonları + `sanitizeSettings` util + null başlangıçlı form alanları.
- **Özellik 14 — Mikrofon Onarımı:** `GET /api/voice/devices` (sounddevice cihaz listesi), `JARVIS_AUDIO_INPUT_DEVICE` override, tarayıcı izin akışı + hata türü bazlı mesajlar.
- **Özellik 15 — v11 Sürümleme:** Tüm sürüm görünümleri `config.JARVIS_VERSION` tek kaynağına bağlandı.
- **Özellik 16 — Performans:** React.lazy + Suspense kod bölme, WS exponential backoff (1→30 sn) + "Yeniden bağlanıyor" banner'ı, GZipMiddleware, sohbet sanal listesi, mobil alt tab navigasyonu.
- **Özellik 17 — Web ATLAS:** `/api/atlas/*` görev kuyruğu (asyncio.Queue, `JARVIS_ATLAS_MAX_CONCURRENT`) + WS adım akışı, AtlasPanel drawer.
- **Özellik 18 — LLM Sıralaması + Fallback:** gemini_provider + deepseek_provider, `llm/router.py` (gemini→deepseek→groq→llama), sağlayıcı seçici dropdown, "Yanıtlayan: X" etiketi, ashiş;d53c; temizleme.
- **Özellik 19 — Konum + Hava:** `/api/location/detect|reverse-geocode|set` (ipapi.co → ip-api.com fallback), `useLocation.ts`, timezone uyumu.

### Altyapı

- Yeni bağımlılıklar (opsiyonel, zarif degrade): `cryptography` (API anahtarı şifreleme), `duckduckgo-search` (web arama; httpx fallback'li).
- Yeni test dosyaları: fact-check, router fallback, kullanıcı API anahtarları, görevler, makrolar, alışkanlıklar, günlük özet, konum, bilgi tabanı, karşılaştırma, eşleştirme debug, kamera durumu.


## [10.0.0] — 2026-10-08

v10.0 "Apex": ATLAS alt sistemine arıza giderme akışı, 4 kademeli akıllı arama, 2026 arayüz estetiği ve 7 yeni yetenek.

### Eklenen

- **Özellik 1 — Otomatik Sunum:** Konu/slayt sayısı/ton bilgisiyle .pptx üretimi (`presentation_builder.py`); zincir: python-pptx → Canva API → PNG slayt seti. İçerik taşması otomatik slayt bölme.
- **Özellik 2 — Tam macOS Desteği:** `platform_service.py` soyutlaması (`WindowsPlatformService` / `MacPlatformService`), macOS Accessibility + Ekran Kaydı izin rehberi, LaunchAgent otomatik başlatma. Tek codebase, tek ürün; dağıtım derlemeleri platform başına ayrı ama bu "ayrı sürüm" değildir.
- **Özellik 3 — ATLAS Arıza Giderme:** `troubleshoot_flow.py` state machine (bekleme → araştırma → uygulama → test → kullanıcı onayı → kapanış/döngü). "+" menüsünden Windows/macOS alt seçimi; çözümler web'den araştırılır (Flash/Pro seçilebilir), bilinen adımlar otomatik uygulanır, "denenenler" listesiyle tekrar yok; tehlikeli işlemler için ek onay; alternatif tükenince manuel öneriler + kaynak linkleri.
- **Özellik 4 — Niyet Algılama + Ayarlar:** `intent_detection.py` (kural tabanlı Türkçe sınıflandırıcı: eylem talebi ↔ bilgi sorusu); "+" menüsünde en üstte ATLAS; ⚙ ayarlar menüsüne "ATLAS'ı Otomatik Aç" toggle'ı — `device_prefs.py` ile IP + makine kimliği bazlı kalıcı saklama.
- **Özellik 5 — Dosya Dönüştürücü:** `file_converter.py`: JPG/PNG→PDF, PDF→JPG/PNG (sayfa sırası korunur), PDF→TXT (image-only PDF'de OCR tespiti), JPG↔PNG. Doğal dille hedef format algılama; desteklenmeyen formatlarda açık yönlendirme.
- **Özellik 6 — Karşılıklı Dışlayıcı Pencereler:** `window_manager.py` — ATLAS açıkken JARVIS gizlenir, ATLAS kapanınca (✕ butonu, "Bitir", çözüldü akışı) JARVIS döner. Tepsi/uyandırma ile JARVIS'i açma girişimi ATLAS aktifken engellenir. Konuşma geçmişi geçişlerde korunur.
- **Özellik 7 — 2026 Arayüz Estetiği:** `status_border.py` (`StatusBorderWidget` + `StatusColorController`): üst durum çubuğu kaldırıldı, yerine tüm kenarı saran ince çerçeve — kırmızı (hata), mavi (çalışma), yeşil (yanıt sonrası tam 12 sn; yeni mesajla anında iptal), idle nefes animasyonu. Tüm geçişler yumuşak interpolasyon. Tüm köşeler ovalleştirildi (butonlar/kartlar/paneller/ATLAS overlay).
- **Özellik 8 — Müfredat + 3 sn Doğrulama:** `data/curriculum.json` (1-12. sınıf, güncellenebilir veri katmanı) + `curriculum.py`; eğitim sorularında 3 saniyelik kendini doğrulama adımı, sınıf seviyesine uygun cevap dili, `✅ Doğrulama` güven raporu.
- **Özellik 9 — Prompt Mimarı:** `prompt_architect.py` — 8 maddelik kalite checklist'i (rol, görev, kısıtlar, varsayımlar, kenar durumlar, çıktı formatı, örnek, doğrulama) ile üretilen prompt'ların self-check'i.
- **Özellik 10 — 4 Kademeli Arama:** `research_engine.py` — Flash Lite (≤5 sn / ~1 sayfa), Flash (~10 sn / ~1,5), Pro (≤40 sn / 2-3 sayfa + kaynak güvenilirlik analizi), Deep Research (10-15 dk / ≤20 sayfa, yuvarlak mm:ss geri sayım `research_ui.py`). Kullanıcı uzunluk isteyince mod varsayılanı geçersizleşir. Güvensiz kaynaklar rapora girmez; yalnızca güvenilir kaynak yoksa "Filtreler" bölümünde Evet/Hayır etiketleriyle sunulur (⚙ ayarından kapatılabilir).

### Altyapı & Dağıtım

- **Paketleme:** `jarvis.spec` (onedir + windowed, `data/curriculum.json` gömülü, playwright hariç ~40 MB tasarruf), `build_installer.py` tek komutlu derleme hattı (sürüm senkronu + PyInstaller + Inno Setup), `installer.iss` (Türkçe kurulum sihirbazı, sihirbaz görselleri), `JARVIS.ico/.icns` + `generate_icon.py`.
- **Sürüm tek kaynak:** `config.APP_VERSION` — pencere başlığı, sistem promptu, kurucu adı tek yerden.
- **Otomatik güncelleme denetimi:** açılıştan ~6 sn sonra arka plan QThread'inde sessiz kontrol (`services/update_check.py`); tercihler cihaz bazlı kalıcı; JARVIS asla kendini indirmez/kurmaz (opt-in).
- **Frozen mod .env:** paketlenmiş EXE `.env`'i EXE yanından okur; anahtarlar bundle'a gömülmez.
- **Lint kapısı:** `ruff.toml` (E9, F821, F811, F841, B023, B033) + F401 temizliği; `requirements.txt`'e `ruff` dev bağımlılığı.
- **Testler:** 242 birim testi (12 dosya), offscreen/gerçek ekran duman testleri, EXE canlı testi, sessiz kurulum/kaldırma uçtan uca testi, gerçek HTTPS güncelleme akışı testi. `JARVIS.exe --self-test` ile frozen doğrulama.

### Düzeltilen

- `automation_engine.py`: `logger` tanımsızdı — WebDriver kapatma ve YouTube oynatma doğrulama bloklarında hata anında except içinde `NameError` üretiliyordu (özellik sessizce çöküyordu). `logger_setup` import'u eklendi.
- `automation_engine.py`: döngü içi lambda'da B023 (geç bağlama) default-arg bağlamasıyla giderildi.
- `services/agent_core.py`, `overlay_ui.py`, `troubleshoot_flow.py`, `intent_detection.py`: ölü kod / kullanılmayan değişkenler temizlendi.
- Sürüm tutarsızlığı: UI'daki sabit "v9.0" etiketleri tek kaynağa (`APP_DISPLAY_VERSION`) bağlandı.

### Notlar

- 1 sayfa ≈ 500 kelime kabul edildi (spec'te netleştirilmemişti).
- OCR için sistem `tesseract` binary'si gerekir; yoksa kullanıcıya "OCR gerekli" bildirilir.
- macOS derlemesi ve izin rehberi manuel testi bir Mac gerektirir (tek makine-dışı kalan iş).
