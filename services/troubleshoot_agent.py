"""
JARVIS v10 APEX PRIME — Sorun Giderme Ajanı
============================================
Kullanıcı "bilgisayarım yavaş" veya "şu program açılmıyor" dediğinde:
  1. Sistem durumunu topla (CPU/RAM/disk, processler, loglar)
  2. Windows Event Viewer'dan son hataları oku
  3. AI ile analiz et
  4. Çözüm adımlarını onayla ve uygula
  5. Forum araması entegre
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from logger_setup import logger
from services.permissions import ActionCategory, get_permission_manager

# ── Sistem durumu toplama ────────────────────────────────────────────────

def collect_system_info() -> dict:
    """CPU, RAM, disk, pil, en yoğun processler."""
    info: dict = {"platform": platform.platform(), "machine": platform.machine()}
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        bat  = psutil.sensors_battery()
        info.update({
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / 1024**3, 1),
            "ram_total_gb": round(mem.total / 1024**3, 1),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / 1024**3, 1),
            "battery_percent": bat.percent if bat else None,
            "battery_charging": bat.power_plugged if bat else None,
        })
        # En yoğun processler
        processes = []
        for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent", "status", "pid"]):
            try:
                p = proc.info
                processes.append({
                    "pid": p["pid"],
                    "name": p["name"],
                    "cpu": p["cpu_percent"] or 0,
                    "ram": p["memory_percent"] or 0,
                    "status": p["status"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        processes.sort(key=lambda x: x["cpu"], reverse=True)
        info["top_processes"] = processes[:15]
    except ImportError:
        info["error"] = "psutil kurulu değil"
    except Exception as exc:
        info["error"] = str(exc)
    return info


def collect_windows_event_log(event_type: str = "Application", max_events: int = 20) -> list[dict]:
    """
    Windows Event Viewer'dan son hataları okur.
    PowerShell Get-WinEvent kullanır.
    """
    if platform.system() != "Windows":
        return []
    try:
        ps_cmd = (
            f"Get-WinEvent -LogName {event_type} -MaxEvents {max_events} "
            f"-ErrorAction SilentlyContinue | "
            f"Where-Object {{$_.LevelDisplayName -in 'Error','Warning'}} | "
            f"Select-Object TimeCreated,LevelDisplayName,Message | "
            f"ConvertTo-Json -Depth 2"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=15, shell=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        import json
        raw = json.loads(result.stdout)
        if isinstance(raw, dict):
            raw = [raw]
        events = []
        for evt in raw[:max_events]:
            events.append({
                "time": str(evt.get("TimeCreated", ""))[:19],
                "level": evt.get("LevelDisplayName", ""),
                "message": str(evt.get("Message", ""))[:300],
            })
        return events
    except Exception as exc:
        logger.warning("[TroubleshootAgent] Event log okunamadı: %s", exc)
        return []


def collect_startup_impact() -> str:
    """Windows'ta başlangıç programlarının etkisini PowerShell ile okur."""
    if platform.system() != "Windows":
        return ""
    try:
        ps_cmd = (
            "Get-CimInstance Win32_StartupCommand | "
            "Select-Object Name,Location,Command | ConvertTo-Json"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=10, shell=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            import json
            items = json.loads(result.stdout)
            if isinstance(items, dict):
                items = [items]
            lines = [f"  • {i.get('Name', '?')}: {i.get('Command', '')[:60]}" for i in items[:10]]
            return "Başlangıç programları:\n" + "\n".join(lines)
    except Exception:
        pass
    return ""


# ── Sorun analizi ────────────────────────────────────────────────────────

def analyze_problem(problem_text: str, system_info: dict, event_log: list[dict], router=None) -> str:
    """
    AI ile sistem durumunu ve hata loglarını analiz eder.
    Returns: Olası nedenler + çözüm adımları (metin)
    """
    # Sistem özetini hazırla
    info_lines = [
        f"Platform: {system_info.get('platform', '?')}",
        f"CPU: %{system_info.get('cpu_percent', '?')}",
        f"RAM: %{system_info.get('ram_percent', '?')} ({system_info.get('ram_used_gb', '?')}/{system_info.get('ram_total_gb', '?')} GB)",
        f"Disk: %{system_info.get('disk_percent', '?')} (boş: {system_info.get('disk_free_gb', '?')} GB)",
    ]
    bat = system_info.get("battery_percent")
    if bat is not None:
        info_lines.append(f"Pil: %{bat} ({'şarjda' if system_info.get('battery_charging') else 'şarjda değil'})")

    top_procs = system_info.get("top_processes", [])[:5]
    if top_procs:
        info_lines.append("En yoğun processler:")
        for p in top_procs:
            info_lines.append(f"  • {p['name']}: CPU %{p['cpu']:.1f}, RAM %{p['ram']:.1f}")

    if event_log:
        info_lines.append(f"\nSon {len(event_log)} hata logu:")
        for evt in event_log[:5]:
            info_lines.append(f"  [{evt['time']}] {evt['level']}: {evt['message'][:120]}")

    context = "\n".join(info_lines)
    prompt = (
        f"Kullanıcının bildirdiği sorun: {problem_text}\n\n"
        f"Mevcut sistem durumu:\n{context}\n\n"
        "Lütfen şunları yap:\n"
        "1. OLASI NEDENLER: 3-5 madde\n"
        "2. ÇÖZÜM ADIMLARI: Her adım için:\n"
        "   [ADIM X] Açıklama\n"
        "   [KOMUT] Çalıştırılabilecek komut (varsa, powershell veya python)\n"
        "   [RİSK] düşük/orta/yüksek\n"
        "3. ÖNLEM: Tekrar olmaması için\n\n"
        "Türkçe, kısa ve net yaz."
    )

    system_prompt = (
        "Sen uzman bir Windows sistem yöneticisi ve IT destek uzmanısın. "
        "Pratik, uygulanabilir çözümler ver. Türkçe konuş."
    )

    if router:
        from services.model_router import TaskType
        return router.chat([], prompt, system_prompt, task_type=TaskType.CHAT)
    else:
        try:
            from services.ai_client import create_groq_client
            key = os.environ.get("JARVIS_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
            client = create_groq_client(key)
            resp = client.chat.completions.create(
                model=os.environ.get("JARVIS_GROQ_MODEL", "openai/gpt-oss-20b"),
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": prompt}],
                max_tokens=1024, temperature=0.5)
            return resp.choices[0].message.content
        except Exception as exc:
            return f"AI analiz hatası: {exc}"


# ── Güvenli çözüm uygulayıcı ────────────────────────────────────────────

def kill_process_by_name(name: str) -> str:
    """Kullanıcı onayıyla process sonlandırır."""
    pm = get_permission_manager()
    result = pm.request(
        ActionCategory.PROCESS_KILL,
        f"'{name}' işlemi sonlandırılacak",
        details=f"Bu process kapatılacak: {name}",
        undo_info="Uygulamayı yeniden başlatarak geri açabilirsiniz.",
    )
    if not result.allowed:
        return f"İşlem sonlandırma iptal edildi."
    try:
        import psutil
        count = 0
        for proc in psutil.process_iter(["name", "pid"]):
            if proc.info["name"].lower() == name.lower():
                proc.terminate()
                count += 1
        return f"{count} '{name}' process'i sonlandırıldı." if count else f"'{name}' çalışmıyor."
    except Exception as exc:
        return f"Process sonlandırma hatası: {exc}"


def clear_temp_files() -> str:
    """Temp dosyaları temizler (onaysız, düşük riskli)."""
    import tempfile
    deleted = 0; freed = 0
    temp_dirs = [
        os.environ.get("TEMP", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
        tempfile.gettempdir(),
    ]
    for d in temp_dirs:
        if not d or not os.path.exists(d):
            continue
        for f in Path(d).rglob("*"):
            try:
                if f.is_file() and f.stat().st_size > 100_000:
                    sz = f.stat().st_size
                    f.unlink()
                    deleted += 1; freed += sz
                    if deleted >= 200:
                        break
            except Exception:
                pass
    return f"{deleted} geçici dosya silindi, {round(freed/1024**2, 1)} MB boşaltıldı."


def restart_service(service_name: str) -> str:
    """Windows servisi yeniden başlatır (onaylı)."""
    if platform.system() != "Windows":
        return "Bu işlem yalnızca Windows'ta destekleniyor."
    pm = get_permission_manager()
    result = pm.request(
        ActionCategory.SYSTEM_CHANGE,
        f"'{service_name}' Windows servisi yeniden başlatılacak",
        details=f"sc stop {service_name} && sc start {service_name}",
        undo_info="Servis yeniden başlatılabilir.",
    )
    if not result.allowed:
        return "Servis yeniden başlatma iptal edildi."
    try:
        subprocess.run(["sc", "stop", service_name], capture_output=True, timeout=15, shell=False)
        import time; time.sleep(2)
        result_start = subprocess.run(["sc", "start", service_name], capture_output=True,
                                      text=True, timeout=15, shell=False)
        if result_start.returncode == 0:
            return f"'{service_name}' servisi yeniden başlatıldı."
        return f"Servis başlatma hatası: {result_start.stderr[:200]}"
    except Exception as exc:
        return f"Servis hatası: {exc}"


# ── Ana TroubleshootAgent sınıfı ─────────────────────────────────────────

class TroubleshootAgent:
    """
    Kullanım:
        agent = TroubleshootAgent(router=get_router())
        result = agent.diagnose("bilgisayarım çok yavaş")
    """

    def __init__(self, router=None):
        self._router = router

    def diagnose(
        self,
        problem: str,
        progress_cb=None,
        notify_cb=None,
    ) -> str:
        """Tam tanı akışını çalıştırır."""
        def _p(step, total, msg):
            if progress_cb:
                progress_cb(step, total, msg)

        total = 4
        _p(1, total, "Sistem durumu toplanıyor...")
        sys_info = collect_system_info()

        _p(2, total, "Hata logları okunuyor...")
        events = collect_windows_event_log("Application", max_events=30)
        sys_events = collect_windows_event_log("System", max_events=20)
        all_events = events + sys_events

        startup = collect_startup_impact()

        _p(3, total, "AI analiz yapıyor...")
        analysis = analyze_problem(problem, sys_info, all_events, self._router)

        _p(4, total, "Rapor hazırlanıyor...")

        # Forum araması (opsiyonel — eğer belirli bir hata kodu varsa)
        import re
        error_code = re.search(r"0x[0-9A-Fa-f]{4,8}|error\s+\d+", problem, re.IGNORECASE)
        forum_result = ""
        if error_code:
            try:
                from jarvis_v11 import search_error_forums
                forum_result = search_error_forums(error_code.group())
            except ImportError:
                pass

        # Raporu birleştir
        lines = [
            "╔══════════════════════════════════════════════╗",
            "  JARVIS SORUN GİDERME RAPORU",
            "╚══════════════════════════════════════════════╝",
            "",
            f"Sorun: {problem}",
            "",
            f"SİSTEM DURUMU:",
            f"  CPU: %{sys_info.get('cpu_percent', '?')} | RAM: %{sys_info.get('ram_percent', '?')} | Disk: %{sys_info.get('disk_percent', '?')}",
        ]

        if sys_info.get("top_processes"):
            lines.append("  En yoğun processler:")
            for p in sys_info["top_processes"][:3]:
                lines.append(f"    • {p['name']}: CPU %{p['cpu']:.1f}")

        if startup:
            lines.append(f"\n{startup}")

        if all_events:
            lines.append(f"\nSON HATA LOGLARINDAN ÖRNEK ({len(all_events)} adet):")
            for evt in all_events[:3]:
                lines.append(f"  [{evt['time']}] {evt['level']}: {evt['message'][:100]}")

        lines.append(f"\nAI ANALİZİ:\n{analysis}")

        if forum_result:
            lines.append(f"\nFORUM ARAŞTIRMASI:\n{forum_result}")

        lines.append("\n══════════════════════════════════════════════")
        lines.append("Yukarıdaki adımları uygulamak ister misiniz?")
        lines.append("'process sonlandır [isim]' veya 'temp temizle' yazabilirsiniz.")

        return "\n".join(lines)
