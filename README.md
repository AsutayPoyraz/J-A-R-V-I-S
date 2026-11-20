🤖 JARVIS v11 "Apex" — Stark Industries 2026
<p align="center">
  <img src="https://img.shields.io/badge/VERSION-v11.0.0_APEX-38BDF8?style=for-the-badge&logo=python&logoColor=white" alt="Version" />
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/PLATFORM-WINDOWS_%7C_MACOS-0EA5E9?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" />
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/STACK-PYTHON_3.11%2B_%7C_PYSIDE6_%7C_FASTAPI-7C3AED?style=for-the-badge&logo=qt&logoColor=white" alt="Stack" />
</p>

> *"Pushing the boundaries of autonomous systems—the pinnacle of desktop artificial intelligence architecture."*

---

🔥 About the Project: Peak Engineering
Designed with the raw power of Python and PySide6, JARVIS v11 "Apex" runs seamlessly across both Windows and macOS from a single unified codebase, engineered to continuously evolve, scale, and expand its capabilities without limits.

Going far beyond a conventional desktop application, JARVIS v11 "Apex" is a showcase of software craftsmanship that unifies AI automation, hardware-level system control, self-healing troubleshooting, and a futuristic 2026 UI aesthetic into a single cohesive ecosystem. Powered by advanced intent recognition, a revolutionary 4-tier search engine, and the ATLAS subsystem capable of controlling your computer at the keyboard and mouse level, this release sets a brand-new standard in developer tooling.

And the best part: this is only the beginning. Its continuously evolving architecture enables it to growth, adapt, and master new superpowers over time.

✨ Core Features & Visual Architecture
2026 UI Aesthetic & Dynamic Glowing Border: Traditional, bulky title bars have been completely replaced with an intelligent, edge-hugging border that dynamically shifts colors based on real-time system state—Red for errors, Blue/Orange for active processing, and a striking Green for success/ready states (held for exactly 12 seconds or immediately overridden upon new user input). Combined with rounded corners and smooth HSL color transitions, it delivers the ultimate Stark OS / Siri desktop experience.

4-Tier Intelligent Search Engine: Seamlessly switch between Flash Lite, Flash, Pro, and Deep Research modes to get anything from instant answers to deep technical and academic analyses backed by strict source reliability filtering.

ATLAS Subsystem & Automated Troubleshooting: A robust self-healing mechanism built to research software errors across the web on Windows and macOS, apply fixes automatically, and verify the resulting system state.

Live Currency & Financial HUD (Kur Paneli): Real-time tracking of live exchange rates (USD/TRY, EUR/TRY, GBP/TRY) seamlessly integrated directly into the dashboard HUD.

Advanced Quick-Access Menus (+ and ⚙): Single-click access to ATLAS, Troubleshooting workflows, Daily Summaries, PDF/File Converters, Speed Test utilities, and device-persistent preferences secured with IP + Machine ID authentication.

Education & Curriculum Support: Provides comprehensive curriculum reference coverage for Grades 1–12, featuring grade-level-appropriate explanations and a built-in 3-second internal self-verification check.

🛠️ Technical Architecture & Modularity
The project is built upon an exceptionally clean, modular, and maintainable Python codebase:

main.py / jarvis_v11.py: Core application entry point and asynchronous QThread worker management.

window_manager.py: Seamless, mutually exclusive state machine governing transitions between JARVIS and ATLAS.

status_border.py: Dynamic border color controller integrated with the intelligent 12-second state timer.

research_engine.py: 4-tier search execution and source reliability filtering engine.

troubleshoot_flow.py: ATLAS error resolution pipelines and automated verification loops.

device_prefs.py: Persistent configuration storage utilizing network IP and permanent Machine ID bindings.

platform_service.py: Clean runtime abstraction layer handling OS-specific logic for Windows and macOS.

📥 Installation & Quick Start
a) Running from Source Code
Prerequisites: Python 3.11+ is required.

Open your terminal in the repository root and run:

python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
python main.py
Note on Platform Services: The base requirements.txt includes the pinned FastAPI and Uvicorn runtime utilized by the services under platform/. To run an individual platform service standalone, use its dedicated entry point and requirements file; the root requirements file will continue to launch the primary main.py desktop application.

b) FastAPI PC Agent (Local Execution)
To launch the real FastAPI PC Agent directly from the repository root:

.\start_fastapi.ps1
API Base URL: http://127.0.0.1:8000

Interactive Documentation (Swagger UI): http://127.0.0.1:8000/api/docs

Alternatively, you can launch the API server via Python directly and override the default host or port flags:

python main.py --api --host 127.0.0.1 --port 8000
c) Cloud Deployment (Render)
The FastAPI backend is structured as a factory application located under platform/pc-agent (rather than main:app). Use the following Render Start Command:

uvicorn --factory jarvis_agent.app:create_app --app-dir platform/pc-agent --host 0.0.0.0 --port $PORT
This exact deployment configuration is also defined in render.yaml.

Health Check Endpoint: /api/health

OpenAPI Documentation: /api/docs

Security & Isolation: Ensure JARVIS_BIND=0.0.0.0 and JARVIS_PAIRING_REQUIRED=1 are set in your production environment so that paired device tokens enforce isolated conversation sessions.

d) Google Home Integration
The Google Home card in the web dashboard communicates with the Google Home Device Access (SDM) API through JARVIS's central backend.

Create a project in the Google Cloud Developer Console, complete Device Access registration, and enable both the SDM API and OAuth 2.0 authentication.

Check Google's current one-time registration fee and terms for Device Access inside the Developer Console (fees and eligibility may vary by region and account type). Features such as live camera streaming may require additional Google Home Developer Console configuration.

Configure the exact OAuth redirect URI inside your Google Cloud Console credentials.

Add the following backend environment variables to your .env file (plain text format):

GOOGLE_HOME_CLIENT_ID=your_client_id_here
GOOGLE_HOME_CLIENT_SECRET=your_client_secret_here
GOOGLE_HOME_PROJECT_ID=your_project_id_here
GOOGLE_HOME_REDIRECT_URI=[https://your-host.example/api/smart-home/oauth/callback](https://your-host.example/api/smart-home/oauth/callback)

# Fernet encryption key or passphrase; use a dedicated secrets manager in production.
GOOGLE_HOME_TOKEN_KEY=your_fernet_token_key_here
Token Security: Refresh tokens are encrypted per user/device owner using Fernet, stored in SQLite, and automatically refreshed prior to expiration.

Command Execution & Polling: Backend commands are dispatched into a bounded queue with strict timeout error handling, and device IDs are validated prior to execution. While event-driven updates via Pub/Sub are supported, this release defaults safely to a 10-second polling interval, sharing the /api/smart-home/devices and /api/smart-home/command endpoints across both the web panel and the in-app card.

e) Environment Configuration (.env)
To securely configure your core API keys and regional settings, create a .env file in the project root directory (or alongside the compiled executable):

JARVIS_GROQ_API_KEY=your_groq_api_key_here
JARVIS_GEMINI_API_KEY=your_gemini_api_key_here
JARVIS_CITY=your_city_here
🔮 Future Vision & Roadmap (An Evolving Ecosystem)
JARVIS v11 "Apex" is not a final destination—it is the most powerful milestone yet in our ongoing AI journey. Upcoming updates include:

Full-Scale Autonomous Voice & Vision: End-to-end autonomous voice command processing paired with deep multimodal visual perception.

Local Smart Home Protocols: Direct local-network protocol integrations with smart home automation hardware.

Cloud Memory & Plugin Marketplace: Cloud-synchronized persistent memory layers and an extensible modular plugin marketplace.

This project stands as a testament to passion, disciplined engineering, and the determination to build the future today. Continuing to evolve, expand, and break boundaries!

🌐 Language Support Note
Currently, JARVIS v11 "Apex" features full Turkish language support out of the box. In upcoming releases, we are expanding global accessibility to include full multi-language support covering English, Italian, French, and more!
