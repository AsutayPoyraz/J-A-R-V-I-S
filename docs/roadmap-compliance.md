# Yol Haritası Uyum Matrisi (Bölüm H)

> **Not (Madde 17):** Orijinal dokümandaki 12 haftalık plan metni bu depoda mevcut
> değil (MEGA_PROMPT.md eski masaüstü mega prompt'unun arşividir). Bu nedenle hafta
> hafta tarih kontrolü yerine **32 maddenin tamamının kod karşısındaki uyum
> denetimi** yapılmıştır. Madde 17 = "KISMEN (kaynak metin yok — ikame denetim bu belge)".

| Madde | Özellik | Durum | Not |
|------|---------|-------|-----|
| 1 | Konuşma modları (resmi/samimi/uyumlu) | ✅ Tamamlandı | `chat/service.py` mod+persona sistem prompt'u; ayarlarda saklanır |
| 2 | QR + 6 haneli PIN eşleştirme (WebSocket) | ✅ Tamamlandı | `routes_pair.py`, JWT imzalı pairing token, süre kontrolü |
| 3 | TR/EN i18n | ✅ Tamamlandı | `platform/web/src/i18n.ts` (TR/EN parite testi var) |
| 4 | Bordo tema (varsayılan) | ✅ Tamamlandı | `index.css` `--accent` bordo; dark/light/maroon |
| 5 | Kayıt/giriş/misafir/şifre sıfırlama | ✅ Tamamlandı | `routes_auth.py` + güvenlik sorusu |
| 6 | Hesaba özel sohbet geçmişi; misafirde kayıt yok | ✅ Tamamlandı | `routes_conversation.py`; misafirde DB yazımı engelli |
| 7 | Kullanıcıya özel ayarlar (DB) | ✅ Tamamlandı | `user_settings` tablosu, hesap bazlı izolasyon |
| 8 | Scroll performansı | ✅ Tamamlandı | `ConversationPanel.tsx` debounce + MutationObserver + passive listener |
| 9 | Sesli komut + ekran analizi + GUI otomasyonu | ✅ Tamamlandı | `routes_voice.py`, `core/screen.py` (vision + pyautogui) |
| 10 | opencv-python bağımlılığı | ✅ Tamamlandı | `requirements.txt` |
| 11 | QR hata düzeltmesi (yeniden dene/geri dönüş) | ✅ Tamamlandı | `PairCard.tsx` retry + PIN fallback |
| 12 | Cihaz algılama paneli | ✅ Tamamlandı | `routes_system.py` user-agent analizi |
| 13 | Otomatik konum + hava durumu (fallback'li) | ✅ Tarayıcı geo → IP fallback → varsayılan şehir |
| 14 | TTS ses ayarları | ✅ Tamamlandı | `voice/tts.py` hız/ton/ses; ayarlar DB'de |
| 15 | Kritik komutlarda 2FA | ✅ Tamamlandı | `twofa.py` + `routes_critical.py` |
| 16 | JWT 15dk/7gün, bcrypt(12), CORS whitelist, rate limit 5/15dk | ✅ Tamamlandı | `auth.py`, `app.py` |
| 17 | 12 haftalık yol haritası uyumu | ⚠️ KISMEN | Kaynak plan metni yok; ikame: bu 32 madde matrisi |
| 18 | Multi-Session Sync + görev zamanlama + bildirim + Memory Bank | ✅ Tamamlandı | `ws.py` broadcast + `reminders/` + memory bank |
| 19 | Smart File Manager / Voice Notes / Screenshot+OCR / Cloud Backup | ⚠️ KISMEN | İlk üç ✅; **OCR = Vision API tabanlı metin çıkarımı** (yerel OCR motoru — Tesseract/EasyOCR — sistemde kurulu olmadığından eklenmedi; yan etkisiz alternatif olarak vision modeli kullanılır) |
| 20 | Shared sessions / Macros / Activity feed / Collaborative notes | ✅ Tamamlandı | Notion/OneNote API'si erişilemediğinden **MD/JSON dışa-içe aktarma MVP** yapıldı (plan gereği raporlandı) |
| 21 | XP/level/görev/rozet/streak/leaderboard | ✅ Tamamlandı | XP **sunucu tarafında** hesaplanır (istemci manipülasyonu korumalı) |
| 22 | Entegrasyonlar + otomasyon + özel komutlar | ✅ Tamamlandı | Google Home/News/WhatsApp + makro yürütücü |
| 23 | Üretkenlik araçları (not/todo) | ✅ Tamamlandı | `routes_productivity.py` |
| 24 | Analytics dashboard + etiketli arama + rapor + JSON/CSV export | ✅ Tamamlandı | `routes_social.py` analytics uçları |
| 25 | E2EE + Privacy Mode + izin yönetimi + audit log (indirilebilir) | ⚠️ KISMEN | **İstemci tarafı E2EE MVP** (AES-GCM, PBKDF2-150k; parola sunucuya gitmez). Gerçek uçtan uca (anahtar değişimi/çoklu cihaz kurtarma) protokolü bu MVP'de yok — sınırlar aşağıda |
| 26 | Sürükle-bırak panel + tema + kişilik + özel palet + erişilebilirlik | ⚠️ KISMEN | Tema/kişilik/palet/a11y ✅; panel sırası ayarlanabilir (metin ile) ancak **gerçek sürükle-bırak yok** |
| 27 | Mola hatırlatıcı + Focus + günlük limit + Mood Tracker | ✅ Tamamlandı | `routes_privacy.py` wellbeing + mood; sohbet stili mood'a uyarlanır |
| 28 | Electron + tarayıcı eklentisi + mobil/saat | ⚠️ KISMEN | Electron (tepsi + Win+J) ✅, Chrome eklentisi ✅, PWA manifest ✅; **mobil native (NFC/AOD) ve akıllı saat uygulaması bu ortamda derlenip imzalanamaz** → API uçları + `docs/mobile-watch-integration.md` hazırlandı |
| 29 | Offline/retry/Render uyku modu | ✅ Tamamlandı | `client.ts` retry + exponential backoff + online/offline |
| 30 | Dosya transferi (50MB + uzantı engeli) | ✅ Tamamlandı | `routes_files.py` + `integrations/files.py` |
| 31 | Sentry (backend+frontend, hassas veri filtreli) | ✅ Tamamlandı | `observability.py` + `sentry.ts`; DSN boşsa no-op |
| 32 | Sohbet paneli konumu (sağ/orta) | ✅ Tamamlandı | `chat_panel_position` ayarı + layout |

## Madde 25 — E2EE MVP sınırları (dürüst rapor)

- ✅ Not başlık+içerik tarayıcıda AES-GCM 256 ile şifrelenir; anahtar PBKDF2-SHA256
  (150.000 tur) ile şifreden türetilir; sunucu yalnızca `v1|salt|iv|ct` opak blob'u görür.
- ❌ Şifre unutulursa veri **kurtarılamaz** (bilinçli tasarım; sunucuda yedek anahtar yok).
- ❌ Çoklu cihaz şifre senkronizasyonu ve doğrulanmış anahtar değişimi (Signal tarzı
  gerçek E2EE) yok — bu bir tarayıcı kasası MVP'sidir, protokol düzeyinde E2EE değildir.

## Elle yapılması gerekenler (platform)

- Electron: `cd platform/desktop && npm install && npm start` (paketi imzalamak için kod imza sertifikası gerekir).
- Eklenti: `platform/extension` klasörünü Chrome'da "Load unpacked" ile yükle.
- Mobil/saat: `docs/mobile-watch-integration.md` içindeki REST/WS sözleşmesini kullan.
- Sentry: `JARVIS_SENTRY_DSN` (backend) ve `VITE_SENTRY_DSN` (web) ortam değişkenlerini gir.
