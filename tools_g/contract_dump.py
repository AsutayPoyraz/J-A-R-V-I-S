# -*- coding: utf-8 -*-
"""G sözleşmesi dökümü: canlı FastAPI app + kaynak dosyaları contract.md'ye yazar."""
import io
import os
import sys

ROOT = r'F:\Software\JARVİS'
AGENT = os.path.join(ROOT, 'platform', 'pc-agent')
OUT = os.path.join(ROOT, 'tools_g', 'contract.md')

sys.path.insert(0, AGENT)
os.chdir(AGENT)

buf = io.StringIO()
w = buf.write

from jarvis_agent.app import app  # noqa: E402

w('# ROUTES\n')
for r in app.routes:
    ms = ','.join(sorted(m for m in getattr(r, 'methods', []) or [] if m not in ('HEAD', 'OPTIONS')))
    w(f"{ms} {getattr(r, 'path', '?')}\n")

try:
    from jarvis_agent.api.routes_settings import SettingsPayload
    w('\n# SETTINGS PAYLOAD (pydantic)\n')
    for name, f in SettingsPayload.model_fields.items():
        w(f"{name}: {f.annotation} | default={f.default!r}\n")
except Exception as e:
    w(f'\n# SettingsPayload ERROR: {e}\n')

for rel in ('jarvis_agent/api/guards.py', 'jarvis_agent/store/section_g.py',
            'jarvis_agent/api/routes_privacy.py', 'tests/test_section_g.py'):
    p = os.path.join(AGENT, rel.replace('/', os.sep))
    w(f'\n# ==== SOURCE: {rel} ====\n')
    try:
        w(io.open(p, encoding='utf-8').read())
    except Exception as e:
        w(f'READ ERROR: {e}\n')

data = buf.getvalue()
io.open(OUT, 'w', encoding='utf-8').write(data)

# compact çıktı: yalnızca rota listesi + payload alan adları
cut = data.find('# SETTINGS PAYLOAD')
print(data[:cut if cut > 0 else 2000])
try:
    from jarvis_agent.api.routes_settings import SettingsPayload
    print('PAYLOAD:', ', '.join(SettingsPayload.model_fields.keys()))
except Exception:
    pass
print('CONTRACT_CHARS=', len(data), 'FILE=', OUT)
