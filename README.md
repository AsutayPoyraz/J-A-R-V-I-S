J.A.R.V.I.S. v11 "Apex" — Stark Industries 2026
"The pinnacle of desktop AI architecture, pushing the boundaries of autonomous systems."
Engineered with the immense power of Python and PySide6, operating seamlessly across both Windows and macOS through a single codebase, this next-generation assistant is built to continuously evolve, scale, and expand its capabilities without limits.
🔥 About the Project: Peak Engineering
J.A.R.V.I.S. v11 "Apex" goes far beyond a standard desktop application; it is a masterclass in software craftsmanship combining AI automation, hardware control, self-healing troubleshooting, and futuristic 2026 UI aesthetics into a single unified ecosystem. 
Featuring advanced intent recognition, a revolutionary 4-tier search engine, and the ATLAS subsystem capable of controlling your computer at the keyboard/mouse level, this version sets a brand-new standard in the developer world. And best of all: This is only the beginning! Its ever-evolving architecture ensures it will continuously grow, adapt, and learn new superpowers. 
🚀 Key Features & Visual Architecture
•	2026 Interface Aesthetics & Dynamic Glow Border: Traditional clunky top bars are completely replaced by an intelligent edge-hugging border that shifts colors dynamically—Red for errors, Blue/Orange for active processing, and a stunning Green for success/ready states (held for precisely 12 seconds or instantly overridden by new user input). Complete with rounded corners and smooth HSL transitions for an ultimate Stark OS / Siri experience. 
•	4-Tier Smart Search Engine: Choose between Flash Lite, Flash, Pro, and Deep Research modes to get instant answers or deep technical/academic analysis backed by strict source reliability filtering. 
•	ATLAS Subsystem & Automated Troubleshooting: A robust self-healing mechanism designed to research software glitches on Windows/macOS via the web, execute fixes automatically, and verify outcomes. 
•	Live Exchange & Financial HUD (Kur Paneli): Real-time tracking of currency rates (USD/TRY, EUR/TRY, GBP/TRY) seamlessly integrated into the dashboard. 
•	Advanced Quick-Access Menus (+ and ⚙): One-click access to ATLAS, Troubleshooting, Daily Briefings, PDF/File Converters, Speedtest tools, and device-persistent preferences backed by IP + Machine ID validation. 
•	Education & Curriculum Support: Full curriculum reference for grades 1–12, providing grade-appropriate explanations paired with a 3-second internal self-validation check.
🛠️ Technical Architecture & Modularity
The project is built on an impeccably clean, modular, and maintainable Python codebase:
•	main.py / jarvis_v11.py: Core entry point and asynchronous QThread worker management. 
•	window_manager.py: Flawless mutually exclusive state machine managing transitions between JARVIS and ATLAS.
•	status_border.py: Dynamic border color controller and smart 12-second timer integration. 
•	research_engine.py: 4-tier search execution and reliability filtering engine. 
•	troubleshoot_flow.py: ATLAS error-resolution and automated testing loops.
•	device_prefs.py: Persistent configuration storage utilizing IP and permanent Machine ID. 
•	platform_service.py: Clean runtime abstraction layer handling OS-specific logic for Windows and macOS.
📥 Installation & Quick Start
a) Running from Source Code
To run the project locally, open your terminal and execute:
Python 3.11+ required
python -m venv .venv
..venv\Scripts\activate # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py

The root requirements include the pinned FastAPI and Uvicorn runtime used by
the services under `platform/`. To run a platform service, use its own entry
point and requirements file; the root `main.py` continues to start the
desktop application.

To start the real FastAPI PC Agent from the repository root:
```powershell
.\start_fastapi.ps1
```
It serves the API at `http://127.0.0.1:8000` and the interactive
documentation at `http://127.0.0.1:8000/api/docs`. The equivalent command is
`python main.py --api`; use `--host` and `--port` to override the defaults.

### Render deployment

The FastAPI app is a factory under `platform/pc-agent`, not `main:app`.
Use this Render Start Command:
```text
uvicorn --factory jarvis_agent.app:create_app --app-dir platform/pc-agent --host 0.0.0.0 --port $PORT
```
The same configuration is available in `render.yaml`. The health check is
`/api/health`, and the OpenAPI documentation is available at `/api/docs`.
Render must keep `JARVIS_BIND=0.0.0.0` and `JARVIS_PAIRING_REQUIRED=1` so
paired device tokens create isolated conversation partitions.

### Google Home bağlantısı

Web panelindeki **Google Home** kartı, Google Home Device Access (SDM)
API'sini JARVIS'in merkezi backend'i üzerinden kullanır. Google Cloud
Developer Console'da bir proje oluşturup Device Access kaydı, SDM API ve
OAuth istemci kimlik bilgilerini etkinleştirin. Device Access kaydı için
Google'ın güncel tek seferlik kayıt ücretini ve uygunluk şartlarını Developer
Console'da kontrol edin; ücret ve şartlar bölgeye/hesap türüne göre
değişebilir. Kamera canlı akışı gibi bazı trait'ler ayrıca Google Home
Developer Console onayı gerektirebilir.

Backend `.env` değerleri:

```text
GOOGLE_HOME_CLIENT_ID=...
GOOGLE_HOME_CLIENT_SECRET=...
GOOGLE_HOME_PROJECT_ID=...
GOOGLE_HOME_REDIRECT_URI=https://your-host.example/api/smart-home/oauth/callback
# Fernet anahtarı veya parola; üretimde gizli yönetim sistemi kullanın.
GOOGLE_HOME_TOKEN_KEY=...
```

OAuth redirect URI'si Google Cloud Console'da birebir tanımlanmalıdır.
Refresh token'ları kullanıcı/cihaz sahibi bazında Fernet ile şifrelenerek
SQLite'a yazılır ve access token süresi dolmadan otomatik yenilenir.
Komutlar backend'de sınırlı bir kuyruğa alınır, zaman aşımında hata olarak
döner ve cihaz kimliği önce kullanıcının listelenen cihazlarıyla doğrulanır.

Pub/Sub ile olay akışı kurmak mümkün olsa da bu sürümde güvenli varsayılan
olarak 10 saniyelik polling kullanılır; web paneli ve uygulama içi kart aynı
`/api/smart-home/devices` ve `/api/smart-home/command` uçlarını kullanır.

b) Configuration (.env)
Create a .env file in the project root directory (or next to the compiled executable) to securely configure your API keys:
JARVIS_GROQ_API_KEY=your_groq_api_key_here
JARVIS_GEMINI_API_KEY=your_gemini_api_key_here
JARVIS_CITY=your_city_here
🔮 Future Vision & Roadmap (An Evolving Ecosystem)
J.A.R.V.I.S. v11 Apex is not a destination—it is the strongest milestone in our ongoing artificial intelligence journey. Upcoming updates include:
•	Full-scale autonomous voice command processing and multi-modal visual perception depth.
•	Native local protocol integrations with smart home automation hardware.
•	Cloud-synchronized memory layers and a modular plugin marketplace.
This project is a testament to passion, coding discipline, and the determination to build the future today. It continues to evolve, expand, and shatter limits!
🌐 Note on Language Support: Currently, J.A.R.V.I.S. v11 Apex features full native Turkish language support. In upcoming project iterations, we are expanding our global reach to include multi-language options such as English, Italian, French, and more!
