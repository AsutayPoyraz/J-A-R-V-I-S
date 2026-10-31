# JARVIS Platform — Faz 1: Yerel Çekirdek

Windows PC'de çalışan kişisel sesli asistan projesinin platform katmanı.
Bu dizin, mevcut JARVIS v10 denemelerinden bağımsız, fazlı geliştirme
sürecinin kalıcı uygulama iskeletidir.

## Mimari (Faz 1)

```
platform/
├── pc-agent/            # Python 3.11+ — Windows'ta çalışan ana servis
│   ├── main.py          # Giriş noktası (uvicorn)
│   ├── jarvis_agent/
│   │   ├── config.py    # .env yükleme + sağlayıcı seçimi
│   │   ├── app.py       # FastAPI uygulama fabrikası + statik UI sunumu
│   │   ├── api/         # REST uçları + WebSocket (her alan kendi modülünde)
│   │   │   ├── routes_system.py        # /api/health, /api/system/stats, hava, audit
│   │   │   ├── routes_chat.py          # /api/chat (LLM + araç döngüsü)
│   │   │   ├── routes_settings.py      # /api/settings (renk, şehir)
│   │   │   ├── routes_conversation.py  # /api/conversation (+ export txt/md)
│   │   │   ├── routes_camera.py        # /api/camera/* (aç/kapa/çek)
│   │   │   └── ws.py                   # /ws/stats (2 sn'de bir canlı itme)
│   │   ├── core/        # stats (psutil monitör), weather (OWM), counters
│   │   ├── llm/         # Sağlayıcı soyutlaması: OpenAI-uyumlu / Anthropic / Mock
│   │   │   ├── provider.py    # ortak arayüz (ChatProvider, ChatResult, ToolCall)
│   │   │   ├── openai_compat.py  # OpenAI + Groq + Ollama (aynı protokol)
│   │   │   ├── anthropic_provider.py
│   │   │   ├── mock_provider.py   # anahtar yokken demo yanıtlar
│   │   │   └── tools.py   # get_system_stats / get_current_time / get_weather
│   │   ├── camera/       # OpenCV kamera servisi (thread-güvenli)
│   │   └── store/        # SQLite: mesajlar, ayarlar, audit log
│   └── tests/           # pytest — 19 test (ağ ve anahtardan bağımsız)
└── web/                 # React 18 + TypeScript + Vite + Tailwind
    └── src/
        ├── App.tsx              # 3 kolonlu düzen (masaüstü) + mobil çekmece
        ├── api/client.ts        # fetch sarmalayıcı + offline algılama
        ├── hooks/useJarvis.ts   # tüm durum yönetimi (WS + REST fallback)
        └── components/          # TopBar, kartlar, CenterStage, sohbet paneli
```

## Teknoloji Seçimleri ve Gerekçeleri

| Katman | Seçim | Gerekçe |
|---|---|---|
| Agent | Python 3.11 + FastAPI + Uvicorn | ASGI WebSocket desteği hazır; OpenAPI dokümantasyon bedava; Faz 3 ses/STT kütüphaneleri zaten Python ekosisteminde |
| İstatistik | psutil | CPU/RAM/disk/uptime için de facto standart |
| Veri | SQLite (stdlib) | Kişisel tek kullanıcı için yeterli; sıfır kurulum |
| LLM | Soyutlama katmanı | Groq/OpenAI/Anthropic/Ollama değiştirilebilir; OpenAI-uyumlu protokol Groq+Ollama'yı da kapsar |
| HTTP | httpx | Sync+async aynı API (hava sync, LLM async) |
| Web UI | React 18 + TS + Vite + Tailwind v3 | İstenen stack; dev'de Vite proxy, üretimde dist agent'ta |
| Hava | OpenWeatherMap | Ücretsiz katman, `lang=tr` Türkçe açıklama |

## Kurulum

### 1) PC Agent

```powershell
cd F:\Software\JARVİS\platform\pc-agent
# mevcut kök .venv ile:
F:\Software\JARVİS\.venv\Scripts\pip install -r requirements.txt
# yeni ortam için:
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Anahtarlar: depo kökündeki `.env` otomatik okunur (JARVIS_GROQ_API_KEY
vb.). Agent'a özel değerler için `platform/pc-agent/.env.example` → `.env`.

> **Kamera (OpenCV) notu (v11):** `opencv-python` requirements içinde yer
> alır; kurulu değilse `GET /api/camera/status` → `opencv_installed: false`
> döner ve arayüz "OpenCV kuruluyor..." modalıyla `POST /api/camera/install`
> çağırır (pip ile otomatik kurar; `JARVIS_CAMERA_AUTO_INSTALL=0` ile
> kapatılabilir). Manuel kurulum: `pip install opencv-python`.
> Ek not: `sounddevice` Windows'ta PortAudio DLL'i gerektirir — pip wheel'i
> birlikte getirir; sorun olursa platform README sounddevice bölümüne bakın.

### 2) Web UI

```powershell
cd F:\Software\JARVİS\platform\web
npm install
npm run build        # dist/ üretir — agent bunu sunar
```

Geliştirme (hot-reload): `npm run dev` → http://localhost:5173
(Vite `/api`'yi 127.0.0.1:8000'e proxy'ler.)

### 3) Çalıştırma

```powershell
cd F:\Software\JARVİS\platform\pc-agent
F:\Software\JARVİS\.venv\Scripts\python main.py
# → http://127.0.0.1:8000
```

Yerel ağ erişimi: `.env`'de `JARVIS_BIND=0.0.0.0`. Loopback dışı bind
adreslerinde QR cihaz eşleştirmesi otomatik olarak zorunludur; telefon
istekleri `X-Device-Token` göndermelidir. TLS için yerel ağda reverse proxy
kullanın.

### 4) Testler

```powershell
cd F:\Software\JARVİS\platform\pc-agent
F:\Software\JARVİS\.venv\Scripts\python -m pytest tests -v
# 19 test — ağa/LLM anahtarına bağımsız (MockProvider)
```

## API Özeti

| Uç | Açıklama |
|---|---|
| `GET /api/health` | Bağlantı + LLM sağlayıcı durumu (offline algılamanın kalbi) |
| `GET /api/system/stats` · `WS /ws/stats` | Canlı CPU/RAM/disk/uptime/sayaçlar (WS 2 sn itme) |
| `POST /api/chat` | Yazılı sohbet; araçlar: saat, sistem, hava |
| `GET/PUT /api/settings` | Arka plan rengi (red/green/blue), şehir |
| `GET/DELETE /api/conversation` + `export?format=txt\|md` | Geçmiş, temizleme, dışa aktarma |
| `POST /api/camera/open\|close\|capture` · `status` | Kamera (kullanıcı eylemi şart) |
| `GET /api/audit` | Denetim kayıtları |
| `/docs` | OpenAPI (Swagger) otomatik dokümantasyon |

## Güvenlik (Faz 1)

- Anahtarlar `.env`'de, `.gitignore` kapsamında; koda yazılmaz.
- LLM'e shell/dosya aracı **yoktur** (kasıtlı) — yalnız okuma araçları.
- Kamera yalnız kullanıcı eylemiyle açılır; LIVE göstergesi; gerekirse
  `JARVIS_CAMERA_DISABLED=1` ile komple kapalı.
- Audit log: her komut/olay SQLite'a yazılır.
- Varsayılan `127.0.0.1`; dış erişim loopback dışı bind'lerde cihaz anahtarıyla korunur.
- Relay ve WoL node secret olmadan başlatılmaz; CORS origin'leri açıkça listelenmelidir.

## Varsayımlar

1. LLM: **Groq** (`openai/gpt-oss-20b`) — kök `.env` anahtarı otomatik.
   `JARVIS_LLM_PROVIDER` ile değiştirilebilir (openai/anthropic/ollama/mock).
2. OWM anahtarı placeholder → Weather kartı bilgilendirme gösterir.
3. Faz 1 yalnız localhost: kimlik doğrulama bilinçli olarak kapsam dışı.
4. LLM'e son 24 mesaj gönderilir (bağlam sınırı).
5. PWA manifest hazır; service worker + kurulum akışı Faz 2'de.

## Faz Durumu (hepsi tamamlandı ve doğrulandı)

| Faz | Kapsam | Durum |
|---|---|---|
| 1 | Yerel çekirdek: agent, web UI, istatistik, sohbet, ayarlar | ✅ |
| 2 | QR eşleştirme, güvenlik katmanı, relay, PWA, WoL | ✅ |
| 3 | Uyandırma ifadeleri, çift alkış, STT/TTS, sesli mod UI | ✅ |
| 4 | Hatırlatıcı/alarm: tekrarlı bildirim, WoL ile uyandırma | ✅ |
| 5 | Mail (IMAP salt-okunur), AI haberleri, dosya transferi | ✅ |
| 6 | Home Assistant (ışık/priz/klima on-off + durum) | ✅ |
| 7 | WhatsApp (CallMeBot tek yönlü) | ✅ |

### Faz 2 — Eşleştirme ve uzaktan erişim

- `jarvis_agent/security.py`: cihaz token tablosu (SQLite), SHA-256 token,
  loopback muafiyeti. `JARVIS_PAIRING_REQUIRED=1` veya `0.0.0.0` bind'da
  loopback dışı **tüm** `/api/*` istekleri `X-Device-Token` ister
  (`/api/health` ve `/api/pair/*` hariç).
- `api/routes_pair.py`: `POST /api/pair/start` (6 haneli, 5 dk ömürlü kod +
  LAN URL), `GET /api/pair/qr.svg` (segno ile SVG QR), `POST /api/pair/claim`,
  `GET /api/pair/status`, `DELETE /api/pair/devices/{id}` (cihaz iptali).
- UI: `PairingGate` (URL'de `?pair=KOD` yakalar), `PairCard` (cihaz listesi).
- PWA: `public/sw.js` (statik kabuk önbelleği; `/api` ve `/ws` asla
  önbelleklenmez), `manifest.webmanifest`, ana ekrana ekle akışı.
- `relay_client.py`: agent'tan relay'e **outbound** WebSocket
  (`/agent-channel?token=`) — router'da port açmaya gerek yok.
- `platform/relay/`: FastAPI relay (agent hub'ı, hatırlatıcı kalıcılığı,
  WoL tetikleme). `platform/wol-node/`: Raspberry Pi/router üzerinde
  magic packet servisi (`POST /wake`, Bearer secret).

### Faz 3 — Sesli mod

- `jarvis_agent/voice/`: `audio.py` (sounddevice girişi), `clap.py`
  (çift alkış — enerji patlaması çift sayımı), `stt.py` (faster-whisper,
  yerel, küçük model), `tts.py` (gTTS, Türkçe ses), `textmatch.py`
  (Türkçe uyandırma/çıkış ifadeleri — normalizasyon + benzerlik),
  `focus_window.py` (barge-in: konuşurken pencere odağı), `service.py`
  (durum makinesi: idle → wake → session; WS ile canlı durum yayını).
- API: `/api/voice/status|start|stop|mode/on|mode/off|say|settings`.
- UI: `CenterStage` sesli mod sahneleri (dinliyor/düşünüyor/konuşuyor),
  `SettingsModal`'da mikrofon/alkış hassasiyeti/otomatik başlatma.
- `.env`: `JARVIS_VOICE_DISABLED=1` ile tüm ses katmanı kapanır.

### Faz 4 — Hatırlatıcılar ve alarmlar

- `reminders/service.py`: SQLite tabanlı; `pending → firing → acked/expired`;
  tekrarlı alarm (REPEAT_EVERY_SECONDS, MAX_REPEATS), kullanıcı etkinliği
  algılanınca susma (`notify_user_activity`), UI onayı (`ack`, `snooze`).
- Agent tick'i + **relay tarafı zamanlayıcı**: PC kapalıyken hatırlatma
  relay'de yaşar; PC'yi uyandırmak gerekirse relay → WoL node → magic packet.
- LLM araçları: `create_reminder`, `list_reminders`, `delete_reminder`,
  `ack_active_alarms` ("tamam, sustur" doğal dilini karşılar).
- UI: `ReminderCard` (liste + form + çalan alarm banner'ı).

### Faz 5-6-7 — Entegrasyonlar

- `integrations/mail.py`: IMAP SSL, salt-okunur INBOX, okunmamışlar.
- `integrations/news.py`: RSS/Atom (stdlib XML), AI + Türkçe teknoloji.
- `integrations/files.py`: `~/JarvisFiles` paylaşım klasörü; ad sanitizasyonu,
  yol kaçışı engelli, 100 MB sınırı, silme ucu yok. `routes_files.py` +
  `FileTransferCard` (yükle/indir).
- `integrations/home.py`: Home Assistant REST; `summarize_states`,
  `control` (yalnız on/off/status — kilit gibi hassas servisler dışarıda).
- `integrations/whatsapp.py`: CallMeBot tek yönlü gönderim (kurulum
  yorumlarda: numara kaydet + onay mesajı + API key).
- Tümü `.env` anahtarlarıyla açılır; yapılandırılmamışsa araçlar zarif
  `{"available": false}` döner, uygulama asla düşmez.

### Relay ve WoL kurulumu

```powershell
# Relay (bulutta ya da her zaman açık bir makinede):
cd platform/relay
pip install -r requirements.txt
JARVIS_RELAY_TOKEN=<güçlü-token> python main.py        # :8001
# Üretimde Caddy/nginx ile TLS önüne alın (wss://).

# WoL node (aynı LAN'da Pi/router):
cd platform/wol-node
pip install -r requirements.txt
JARVIS_WOL_SECRET=<secret> python main.py              # :8080

# Agent (.env):
JARVIS_RELAY_URL=wss://relay.example.com
JARVIS_RELAY_TOKEN=<güçlü-token>
JARVIS_WOL_NODE_URL=http://<pi-ip>:8080
JARVIS_WOL_NODE_SECRET=<secret>
JARVIS_TARGET_MAC=AA-BB-CC-DD-EE-FF
```

### Doğrulama

- `pytest tests -q` → **54 test** (agent, hatırlatıcı, pairing/faz2,
  int57 köprüsü) — ağ ve anahtardan bağımsız.
- `npm run build` → temiz TS derlemesi.
- Canlı duman testi: health, stats, pair start/QR/status, settings,
  reminder oluştur/liste/sil, files, voice status, chat (mock) ve
  `/sw.js` sunumu — tümü HTTP 200; relay bağlantısı `connected: true`.
