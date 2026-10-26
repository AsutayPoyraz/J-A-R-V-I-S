# -*- coding: utf-8 -*-
"""G web yamasi 2: PrivacyWellnessCard.tsx uretimi (madde 25-27 arayuzu).
Parca A: sozlesme turetme. Parca B (S2B): sablon + yazma."""
import re, json, pathlib
R = pathlib.Path(r"F:\Software\JARVİS")
WEB, AG = R / "platform" / "web", R / "platform" / "pc-agent"
JA = AG / "jarvis_agent"
def log(*a): print("[s2]", *a, flush=True)

rs = (JA / "api" / "routes_settings.py").read_text(encoding="utf-8")
pf = set(re.findall(r"payload\.([a-z_]+)", rs))
cfg = (JA / "config.py").read_text(encoding="utf-8")
def consts(name):
    m = re.search(name + r"\s*=\s*[\[(](.*?)[\])]", cfg, re.S)
    if not m:
        return []
    return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]
WIDGETS = consts("ALLOWED_WIDGETS")
PERSONAS = consts("ALLOWED_PERSONA_STYLES")
MOODS = consts("MOODS")
if not MOODS:
    sgp = JA / "store" / "section_g.py"
    if sgp.exists():
        m = re.search(r"MOODS\s*=\s*\{([^}]*)\}", sgp.read_text(encoding="utf-8"), re.S)
        if m:
            MOODS = re.findall(r'"([a-z_-]+)"\s*:', m.group(1))
log("W=%s" % WIDGETS); log("P=%s" % PERSONAS); log("M=%s" % MOODS)

pr = (JA / "api" / "routes_privacy.py").read_text(encoding="utf-8")
eps = [(m.group(1).upper(), m.group(2)) for m in re.finditer(r'@router\.(get|post|put|patch|delete)\(\s*"([^"]+)"', pr)]
mr = re.search(r"APIRouter\(([^)]*)\)", pr)
pfx = ""
if mr:
    pm = re.search(r'prefix\s*=\s*"([^"]+)"', mr.group(1))
    if pm:
        pfx = pm.group(1)
eps = [(m, p if p.startswith("/api") else pfx + p) for m, p in eps]
log("eps:", eps)
def ep(kw, method):
    for m, p in eps:
        if kw in p and m == method:
            return p
    return None
EP_MODE = ep("mode", "POST") or ep("state", "POST")
EP_PG = ep("permission", "GET")
EP_PP = ep("permission", "POST")
EP_AD = ep("download", "GET")
log("EP_MODE=%s PG=%s PP=%s AD=%s" % (EP_MODE, EP_PG, EP_PP, EP_AD))

csrc = (WEB / "src" / "api" / "client.ts").read_text(encoding="utf-8")
mg = re.search(r"export async function (\w*[Ss]ettings\w*)\(\s*\)", csrc)
GETFN = mg.group(1) if mg else None
mu = re.search(r"export async function (update\w*)\(", csrc)
UPDFN = mu.group(1) if mu else None
i18 = (WEB / "src" / "i18n.ts").read_text(encoding="utf-8")
HAS_T = bool(re.search(r"export (?:async )?function t\b|export const t\b", i18))
log("GET=%s UPD=%s t=%s" % (GETFN, UPDFN, HAS_T))
if not (GETFN and UPDFN and HAS_T):
    log("SKIP: on kosler eksik (once s1 calismali)")
    raise SystemExit(0)

FN = []
if EP_MODE:
    FN.append("gSetPrivacyMode")
if EP_PG:
    FN += ["gGetPermissions", "gSetPermission"]
if EP_AD:
    FN.append("gDownloadAudit")
# ---S2B---
