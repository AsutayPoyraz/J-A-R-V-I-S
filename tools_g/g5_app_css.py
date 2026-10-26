# -*- coding: utf-8 -*-
"""G5: wire PrivacyWellnessCard into App.tsx, append a11y CSS, ensure web .env SENTRY_DSN, write g_report.txt."""
import io, re, os, json, glob, sys

R = ([p for p in glob.glob("F:/Software/JARV*") if os.path.isdir(p) and os.path.exists(p + "/platform")] or [""])[0]
W = R + "/platform/web/src"
def rd(p):
    try: return io.open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception: return ""

# --- App.tsx: import + render
A = W + "/App.tsx"
a = rd(A); app_ok = False
if "PrivacyWellnessCard" in a:
    print("G5: app SKIP (already)"); app_ok = True
else:
    lines = a.split("\n")
    ai = None
    for i, ln in enumerate(lines):
        if re.match(r'\s*<SocialCard\b', ln): ai = i; break
    if ai is None:
        for i, ln in enumerate(lines):
            if re.match(r'\s*<AgentCard\b', ln): ai = i; break
    if ai is None:
        print("G5: app render anchor NOT FOUND (skipping app patch)")
    else:
        j, end = ai, -1
        while j < min(ai + 8, len(lines)):
            s2 = lines[j].strip()
            if s2.endswith("/>"): end = j; break
            j += 1
        if end < 0 and lines[ai].strip().endswith("/>"): end = ai
        if end < 0:
            print("G5: card self-close NOT FOUND (skipping app patch)")
        else:
            indent = re.match(r'\s*', lines[ai]).group(0)
            lines.insert(end + 1, indent + "<PrivacyWellnessCard />")
            ii = None
            for i, ln in enumerate(lines):
                if 'from "./components/SocialCard"' in ln: ii = i; break
            if ii is None:
                for i, ln in enumerate(lines):
                    if 'from "./components/AgentCard"' in ln: ii = i; break
            if ii is not None:
                lines.insert(ii + 1, 'import PrivacyWellnessCard from "./components/PrivacyWellnessCard";')
            io.open(A, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
            print("G5: app wired (import+render)"); app_ok = True

# --- index.css: a11y styles
S = W + "/index.css"
s = rd(S)
if "__SECTION_G_CSS__" not in s:
    css = """

/* __SECTION_G_CSS__ : accessibility + privacy card (Section G) */
[data-font-scale="sm"] { font-size: 14px; }
[data-font-scale="md"] { font-size: 16px; }
[data-font-scale="lg"] { font-size: 18px; }
[data-a11y-font="dyslexic"] body, [data-a11y-font="dyslexic"] button, [data-a11y-font="dyslexic"] input,
[data-a11y-font="dyslexic"] select, [data-a11y-font="dyslexic"] textarea {
  font-family: "OpenDyslexic", "Comic Sans MS", Verdana, sans-serif !important; letter-spacing: 0.03em; line-height: 1.6;
}
[data-contrast="high"] { --primary: #ffd400; --text: #ffffff; --bg: #000000; }
[data-contrast="high"] body { background: #000; color: #fff; }
[data-contrast="high"] .card, [data-contrast="high"] .pw-note { border-color: #ffd400; }
.pw-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.pw-tab { border: 1px solid var(--border, #bbb3); background: transparent; border-radius: 8px; padding: 3px 9px; font-size: 12px; cursor: pointer; }
.pw-tab.pw-on { background: var(--primary, #8B0000); color: #fff; border-color: transparent; }
.pw-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin: 5px 0; }
.pw-row input[type="text"], .pw-row input[type="password"], .pw-row input[type="number"], .pw-row textarea, .pw-row select { flex: 1; min-width: 0; }
.pw-desc { opacity: 0.75; font-size: 12px; margin: 4px 0; }
.pw-note { border: 1px solid var(--border, #bbb3); border-radius: 8px; padding: 6px 9px; margin: 6px 0; }
.pw-mood { display: flex; gap: 6px; flex-wrap: wrap; }
.pw-chip { display: inline-block; border: 1px solid #8883; border-radius: 999px; padding: 1px 8px; margin: 2px; font-size: 11px; }
.pw-err { color: #dc2626; font-size: 12px; margin: 4px 0; }
.pw-ok { color: #15803d; font-size: 12px; margin: 4px 0; }
.pw-body { white-space: pre-wrap; font-size: 12px; margin: 4px 0 0; }
"""
    io.open(S, "w", encoding="utf-8", newline="\n").write(s.rstrip("\n") + css)
    print("G5: css appended")
else:
    print("G5: css SKIP")

# --- web .env.example: SENTRY_DSN
E = R + "/platform/web/.env.example"
try:
    e = rd(E)
    if e is not None and "SENTRY_DSN" not in e:
        io.open(E, "a", encoding="utf-8", newline="\n").write("\n# Sentry (hassas veri filtreli; bos ise kapali)\nVITE_SENTRY_DSN=\n")
        print("G5: web .env.example + SENTRY_DSN")
    else:
        print("G5: web env SKIP")
except Exception as ex:
    print("G5: env err", ex)

# --- report
rep = {"app_wired": app_ok,
       "types": "__SECTION_G__" in rd(W + "/types.ts") or "Section G: Privacy" in rd(W + "/types.ts"),
       "client": "__SECTION_G_CLIENT__" in rd(W + "/api/client.ts") or "__SECTION_G_CLIENT__" in rd(W + "/client.ts"),
       "i18n": "__G_I18N__" in rd(W + "/i18n.ts"),
       "card": os.path.exists(W + "/components/PrivacyWellnessCard.tsx") and "__G_PART2__" not in rd(W + "/components/PrivacyWellnessCard.tsx"),
       "css": "__SECTION_G_CSS__" in rd(W + "/index.css")}
try:
    cj = json.load(io.open(R + "/tools_g/g_contract.json", encoding="utf-8"))
    rep["contract"] = {k: v for k, v in cj.items() if isinstance(v, (str, type(None)))}
except Exception:
    pass
os.makedirs(R + "/tools_g", exist_ok=True)
json.dump(rep, io.open(R + "/tools_g/g_report.txt", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("G5: report ->", json.dumps({k: v for k, v in rep.items() if k != "contract"}))