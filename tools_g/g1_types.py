# -*- coding: utf-8 -*-
"""G1: Append Section G types to web/src/types.ts (idempotent)."""
import io, glob, os, sys

R = ([p for p in glob.glob("F:/Software/JARV*") if os.path.isdir(p) and os.path.exists(p + "/platform")] or [""])[0]
P = R + "/platform/web/src/types.ts"
try:
    src = io.open(P, encoding="utf-8-sig").read()
except Exception as e:
    print("G1: FAIL read", e); sys.exit(0)

MARK = "// ===== Section G: Privacy / Wellness / A11y (auto) ====="
if MARK in src:
    print("G1: SKIP (already applied)"); sys.exit(0)

block = MARK + """
export interface PrivacyNoteItem { id: string; title: string; created_at?: string; content?: string; [k: string]: unknown; }
export interface PrivacyVaultStatus { locked?: boolean; auto_lock_minutes?: number; privacy_mode?: boolean; [k: string]: unknown; }
export interface PermissionState { [k: string]: boolean; }
export interface AuditLogEntry { id?: string; ts?: string; action?: string; detail?: string; [k: string]: unknown; }
export interface MoodEntryItem { id?: string; mood?: string; note?: string; ts?: string; [k: string]: unknown; }
export interface WellbeingSummaryData { focus_mode?: boolean; daily_limit?: number; used_today?: number; last_mood?: string; [k: string]: unknown; }
export interface GAccessibilitySettings { font_size?: string; dyslexic_font?: boolean; high_contrast?: boolean; [k: string]: unknown; }
"""
io.open(P, "w", encoding="utf-8", newline="\n").write(src.rstrip("\n") + "\n\n" + block)
print("G1: OK types.ts appended")