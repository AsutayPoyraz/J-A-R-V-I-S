# -*- coding: utf-8 -*-
"""Geçici: README.md İngilizce tanıtım metinlerinde v10 → v11."""

P = r"f:\Software\JARVİS\README.md"
src = open(P, encoding="utf-8").read()
replacements = [
    (
        'J.A.R.V.I.S. v10.0 "Apex" goes far beyond',
        'J.A.R.V.I.S. v11 "Apex" goes far beyond',
    ),
    (
        "J.A.R.V.I.S. v10.0 Apex is not a destination",
        "J.A.R.V.I.S. v11 Apex is not a destination",
    ),
    (
        "Currently, J.A.R.V.I.S. v10.0 Apex features full native Turkish language support.",
        "Currently, J.A.R.V.I.S. v11 Apex features full native Turkish language support.",
    ),
]
count = 0
for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        count += 1
open(P, "w", encoding="utf-8", newline="\n").write(src)
print(f"README.md: {count}/3 v10→v11 replacement applied")
