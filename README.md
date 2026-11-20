# 🤖 JARVIS v11 "Apex" — Stark Industries 2026

<p align="center">
  <img src="https://img.shields.io/badge/VERSION-v11.0.0_APEX-38BDF8?style=for-the-badge&logo=python&logoColor=white" alt="Version" />
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/PLATFORM-WINDOWS_%7C_MACOS-0EA5E9?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" />
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/STACK-PYTHON_3.11%2B_%7C_PYSIDE6_%7C_FASTAPI-7C3AED?style=for-the-badge&logo=qt&logoColor=white" alt="Stack" />
</p>

> *"Pushing the boundaries of autonomous systems—the pinnacle of desktop artificial intelligence architecture."*

---

## 🔥 About the Project: Peak Engineering

Designed with the raw power of **Python** and **PySide6**, **JARVIS v11 "Apex"** runs seamlessly across both **Windows** and **macOS** from a single unified codebase, engineered to continuously evolve, scale, and expand its capabilities without limits.

Going far beyond a conventional desktop application, JARVIS v11 "Apex" is a showcase of software craftsmanship that unifies AI automation, hardware-level system control, self-healing troubleshooting, and a futuristic 2026 UI aesthetic into a single cohesive ecosystem. Powered by advanced intent recognition, a revolutionary 4-tier search engine, and the **ATLAS** subsystem capable of controlling your computer at the keyboard and mouse level, this release sets a brand-new standard in developer tooling.

And the best part: **this is only the beginning.** Its continuously evolving architecture enables it to grow, adapt, and master new superpowers over time.

---

## ✨ Core Features & Visual Architecture

* **2026 UI Aesthetic & Dynamic Glowing Border:** Traditional, bulky title bars have been completely replaced with an intelligent, edge-hugging border that dynamically shifts colors based on real-time system state—**Red** for errors, **Blue/Orange** for active processing, and a striking **Green** for success/ready states (held for exactly 12 seconds or immediately overridden upon new user input). Combined with rounded corners and smooth HSL color transitions, it delivers the ultimate Stark OS / Siri desktop experience.
* **4-Tier Intelligent Search Engine:** Seamlessly switch between **Flash Lite**, **Flash**, **Pro**, and **Deep Research** modes to get anything from instant answers to deep technical and academic analyses backed by strict source reliability filtering.
* **ATLAS Subsystem & Automated Troubleshooting:** A robust self-healing mechanism built to research software errors across the web on Windows and macOS, apply fixes automatically, and verify the resulting system state.
* **Live Currency & Financial HUD (`Kur Paneli`):** Real-time tracking of live exchange rates (`USD/TRY`, `EUR/TRY`, `GBP/TRY`) seamlessly integrated directly into the dashboard HUD.
* **Advanced Quick-Access Menus (`+` and `⚙`):** Single-click access to ATLAS, Troubleshooting workflows, Daily Summaries, PDF/File Converters, Speed Test utilities, and device-persistent preferences secured with `IP + Machine ID` authentication.
* **Education & Curriculum Support:** Provides comprehensive curriculum reference coverage for **Grades 1–12**, featuring grade-level-appropriate explanations and a built-in 3-second internal self-verification check.

---

## 🛠️ Technical Architecture & Modularity

The project is built upon an exceptionally clean, modular, and maintainable Python codebase:

* **`main.py` / `jarvis_v11.py`:** Core application entry point and asynchronous `QThread` worker management.
* **`window_manager.py`:** Seamless, mutually exclusive state machine governing transitions between JARVIS and ATLAS.
* **`status_border.py`:** Dynamic border color controller integrated with the intelligent 12-second state timer.
* **`research_engine.py`:** 4-tier search execution and source reliability filtering engine.
* **`troubleshoot_flow.py`:** ATLAS error resolution pipelines and automated verification loops.
* **`device_prefs.py`:** Persistent configuration storage utilizing network IP and permanent Machine ID bindings.
* **`platform_service.py`:** Clean runtime abstraction layer handling OS-specific logic for Windows and macOS.

---

## 📥 Installation & Quick Start

### a) Running from Source Code

**Prerequisites:** `Python 3.11+` is required.

Open your terminal in the repository root and run:

```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
python main.py
