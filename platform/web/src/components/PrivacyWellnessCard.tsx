/**
 * Bölüm G kartı (madde 25/26/27): Gizlilik kasası, hassas işlem izinleri,
 * güvenlik denetim kaydı, sağlık/odak ve erişilebilirlik.
 *
 * - Madde 25 (E2EE MVP): Notlar tarayıcıda AES-GCM (PBKDF2-SHA256, 150k tur)
 *   ile şifrelenir; sunucu yalnızca opak "v1|salt|iv|ct" dizisini saklar ve
 *   parola asla gönderilmez. Sınırlar FİNAL raporunda "KISMEN" olarak notlu.
 * - Tüm kullanıcıya görünür metinler i18n'den gelir (madde 3).
 */
import { useCallback, useEffect, useState } from "react";
import Card from "./Card";
import {
  api,
  auditCsv,
  createPrivacyNote,
  deletePrivacyNote,
  fetchPrivacyAudit,
  fetchPrivacyNotes,
  fetchPrivacyPermissions,
  fetchWellbeing,
  putMood,
  setPrivacyPermission,
} from "../api/client";
import { t } from "../i18n";
import type { AuditLogEntry, PermissionState, PrivacyNoteItem } from "../types";

// ── WebCrypto yardımcıları (madde 25) ────────────────────────────────────────
const te = new TextEncoder();
const td = new TextDecoder();

function b64(buf: ArrayBuffer): string {
  const b = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]);
  return btoa(s);
}
function ub64(s: string): Uint8Array {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
async function deriveKey(pass: string, salt: Uint8Array): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey("raw", te.encode(pass), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: 150000, hash: "SHA-256" },
    base,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}
/** Metni "v1|salt|iv|ct" biçiminde şifreler (parçalar base64). */
async function sealText(pass: string, text: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(pass, salt);
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, te.encode(text));
  return `v1|${b64(salt.buffer as ArrayBuffer)}|${b64(iv.buffer as ArrayBuffer)}|${b64(ct)}`;
}
/** Şifreli metni açar; parola yanlışsa DOMException fırlatır. */
async function openSealed(pass: string, blob: string): Promise<string> {
  const [v, saltB, ivB, ctB] = blob.split("|");
  if (v !== "v1" || !saltB || !ivB || !ctB) throw new Error("format");
  const key = await deriveKey(pass, ub64(saltB));
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: ub64(ivB) }, key, ub64(ctB));
  return td.decode(pt);
}
/** Erişilebilirlik ayarlarını <html> özniteliklerine yansıtır (madde 26). */
function applyA11y(s: Record<string, unknown>): void {
  const el = document.documentElement;
  if (s.dyslexic_font) el.dataset.a11yFont = "dyslexic";
  else delete el.dataset.a11yFont;
  if (s.high_contrast) el.dataset.a11yContrast = "high";
  else delete el.dataset.a11yContrast;
  const scale = typeof s.font_scale === "number" ? s.font_scale : 1;
  el.style.fontSize = scale !== 1 ? `${Math.round(16 * scale)}px` : "";
}

type Tab = "privacy" | "permissions" | "audit" | "wellness" | "a11y";
const TABS: Tab[] = ["privacy", "permissions", "audit", "wellness", "a11y"];

const inputCls =
  "w-full rounded border border-white/10 bg-black/20 px-2 py-1 text-xs text-slate-200 outline-none focus:border-white/25";
const btnCls = "rounded border border-white/10 px-2 py-1 text-xs hover:bg-white/10 disabled:opacity-50";

export default function PrivacyWellnessCard() {
  const [tab, setTab] = useState<Tab>("privacy");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  // Gizlilik kasası + sağlık (tek wellbeing satırından beslenir)
  const [wb, setWb] = useState<Record<string, unknown>>({});
  const [notes, setNotes] = useState<PrivacyNoteItem[]>([]);
  const [pass, setPass] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newBody, setNewBody] = useState("");
  const [revealed, setRevealed] = useState<Record<number, string>>({});
  const [noteErr, setNoteErr] = useState("");

  // İzinler + denetim
  const [perms, setPerms] = useState<PermissionState>({});
  const [known, setKnown] = useState<string[]>([]);
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);

  // Sağlık (madde 27)
  const [focusMode, setFocusMode] = useState(false);
  const [breakMin, setBreakMin] = useState("0");
  const [dailyMin, setDailyMin] = useState("0");

  // Erişilebilirlik / kişilik (madde 26)
  const [fontScale, setFontScale] = useState(1);
  const [dyslexic, setDyslexic] = useState(false);
  const [contrast, setContrast] = useState(false);
  const [personaName, setPersonaName] = useState("");
  const [personaStyle, setPersonaStyle] = useState("");
  const [styles, setStyles] = useState<string[]>([]);
  const [widgets, setWidgets] = useState("");

  const flash = (m: string) => {
    setMsg(m);
    setErr("");
    window.setTimeout(() => setMsg(""), 2200);
  };
  const fail = (e: unknown) =>
    setErr(`${t("g.common.error")}: ${e instanceof Error ? e.message : String(e)}`);

  const loadPrivacy = useCallback(async () => {
    try {
      const [w, n] = await Promise.all([fetchWellbeing(), fetchPrivacyNotes()]);
      const row = (w ?? {}) as Record<string, unknown>;
      setWb(row);
      setFocusMode(Boolean(row.focus_mode));
      setBreakMin(String(Number(row.break_reminder_minutes ?? 0)));
      setDailyMin(String(Number(row.daily_limit_minutes ?? 0)));
      setNotes(((n as { notes?: PrivacyNoteItem[] })?.notes ?? []) as PrivacyNoteItem[]);
      setErr("");
    } catch (e) {
      fail(e);
    }
  }, []);

  const loadPerms = useCallback(async () => {
    try {
      const r = (await fetchPrivacyPermissions()) as {
        permissions?: PermissionState;
        known?: string[];
      };
      setPerms(r?.permissions ?? {});
      setKnown(r?.known ?? []);
      setErr("");
    } catch (e) {
      fail(e);
    }
  }, []);

  const loadAudit = useCallback(async () => {
    try {
      const r = (await fetchPrivacyAudit()) as { entries?: AuditLogEntry[] };
      setEntries(r?.entries ?? []);
      setErr("");
    } catch (e) {
      fail(e);
    }
  }, []);

  const loadA11y = useCallback(async () => {
    try {
      const s = (await api.settings()) as unknown as Record<string, unknown>;
      setFontScale(typeof s.font_scale === "number" ? s.font_scale : 1);
      setDyslexic(Boolean(s.dyslexic_font));
      setContrast(Boolean(s.high_contrast));
      setPersonaName(String(s.persona_name ?? ""));
      setPersonaStyle(String(s.persona_style ?? ""));
      setStyles(Array.isArray(s.allowed_persona_styles) ? (s.allowed_persona_styles as string[]) : []);
      setWidgets(Array.isArray(s.dashboard_layout) ? (s.dashboard_layout as string[]).join(", ") : "");
    } catch (e) {
      fail(e);
    }
  }, []);

  // İlk yükleme: gizlilik verisi + a11y özniteliklerini erken uygula
  useEffect(() => {
    void loadPrivacy();
    void api
      .settings()
      .then((s) => applyA11y(s as unknown as Record<string, unknown>))
      .catch(() => undefined);
  }, [loadPrivacy]);

  // Sekme değişince ilgili veriyi getir (basit geç yükleme)
  useEffect(() => {
    if (tab === "permissions") void loadPerms();
    else if (tab === "audit") void loadAudit();
    else if (tab === "a11y") void loadA11y();
  }, [tab, loadPerms, loadAudit, loadA11y]);

  // ── Eylemler ────────────────────────────────────────────────────────────────
  const togglePrivacyMode = async () => {
    setBusy(true);
    try {
      await api.updateSettings({ privacy_mode: !wb.privacy_mode });
      await loadPrivacy();
      flash(t("g.common.done"));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const addNote = async () => {
    setNoteErr("");
    if (!pass || pass.length < 4) {
      setNoteErr(t("g.privacy.decrypt_err"));
      return;
    }
    if (!newTitle.trim() || !newBody.trim()) return;
    setBusy(true);
    try {
      await createPrivacyNote({
        title_cipher: await sealText(pass, newTitle.trim()),
        body_cipher: await sealText(pass, newBody.trim()),
      });
      setNewTitle("");
      setNewBody("");
      setRevealed({});
      await loadPrivacy();
      flash(t("g.common.done"));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const reveal = async (n: PrivacyNoteItem) => {
    setNoteErr("");
    const row = n as unknown as Record<string, unknown>;
    try {
      const title = await openSealed(pass, String(row.title_cipher ?? ""));
      const body = await openSealed(pass, String(row.body_cipher ?? ""));
      setRevealed((r) => ({ ...r, [Number(n.id)]: `${title}\n\n${body}` }));
    } catch {
      setNoteErr(t("g.privacy.decrypt_err"));
    }
  };

  const delNote = async (id: number) => {
    setBusy(true);
    try {
      await deletePrivacyNote(id);
      await loadPrivacy();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const togglePerm = async (key: string, allowed: boolean) => {
    setPerms((p) => ({ ...p, [key]: allowed })); // iyimser güncelleme
    try {
      await setPrivacyPermission(key, allowed);
    } catch (e) {
      setPerms((p) => ({ ...p, [key]: !allowed }));
      fail(e);
    }
  };

  const downloadAudit = async () => {
    try {
      const blob = await auditCsv(90);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "jarvis-security-audit.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      fail(e);
    }
  };

  const setMood = async (m: string) => {
    setBusy(true);
    try {
      await putMood(m);
      await loadPrivacy();
      flash(t("g.common.done"));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const saveWellness = async () => {
    setBusy(true);
    try {
      await api.updateSettings({
        focus_mode: focusMode,
        break_reminder_minutes: Math.max(0, Math.min(240, Number(breakMin) || 0)),
        daily_limit_minutes: Math.max(0, Math.min(1440, Number(dailyMin) || 0)),
      });
      await loadPrivacy();
      flash(t("g.common.done"));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const saveA11y = async () => {
    setBusy(true);
    try {
      const layout = widgets
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      await api.updateSettings({
        font_scale: fontScale,
        dyslexic_font: dyslexic,
        high_contrast: contrast,
        persona_name: personaName.trim(),
        persona_style: personaStyle || undefined,
        dashboard_layout: layout,
      });
      applyA11y({ font_scale: fontScale, dyslexic_font: dyslexic, high_contrast: contrast });
      flash(t("g.common.done"));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

    const refreshAll = useCallback(async () => {
    if (tab === "permissions") await loadPerms();
    else if (tab === "audit") await loadAudit();
    else await loadPrivacy();
  }, [tab, loadPerms, loadAudit, loadPrivacy]);

  const moodKeys: Array<[string, string]> = [
    ["neutral", "g.wellness.mood_neutral"],
    ["focused", "g.wellness.mood_focused"],
    ["tired", "g.wellness.mood_tired"],
    ["stressed", "g.wellness.mood_stressed"],
    ["cheerful", "g.wellness.mood_cheerful"],
  ];

  return (
    <Card title={t("g.privacy.title")} onRefresh={refreshAll} refreshing={busy}>
      {err && <p style={{ color: "#fca5a5", fontSize: 12, margin: "0 0 6px" }}>{err}</p>}
      {msg && <p style={{ color: "#86efac", fontSize: 12, margin: "0 0 6px" }}>{msg}</p>}

      {/* Sekmeler */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
        {TABS.map((tb) => (
          <button
            key={tb}
            type="button"
            onClick={() => setTab(tb)}
            className={btnCls}
            style={{ opacity: tab === tb ? 1 : 0.6, background: tab === tb ? "rgba(255,255,255,.08)" : undefined }}
          >
            {t(`g.tabs.${tb}`)}
          </button>
        ))}
      </div>

      {/* ── Gizlilik kasası (madde 25) ── */}
      {tab === "privacy" && (
        <div style={{ display: "grid", gap: 8 }}>
          <div>
            <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
              <input type="checkbox" checked={Boolean(wb.privacy_mode)} onChange={togglePrivacyMode} disabled={busy} />
              <span>{t("g.privacy.mode")}</span>
            </label>
            <p style={{ fontSize: 11, opacity: 0.7, margin: "2px 0 0" }}>{t("g.privacy.mode_desc")}</p>
          </div>

          <p style={{ fontSize: 11, opacity: 0.75, margin: 0 }}>{t("g.privacy.desc")}</p>

          <div style={{ display: "grid", gap: 4 }}>
            <input className={inputCls} type="password" placeholder={t("g.common.passphrase")} value={pass} onChange={(e) => setPass(e.target.value)} />
            <input className={inputCls} placeholder={t("g.privacy.new_title")} value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
            <textarea className={inputCls} rows={2} placeholder={t("g.privacy.new_body")} value={newBody} onChange={(e) => setNewBody(e.target.value)} />
            <button type="button" className={btnCls} onClick={addNote} disabled={busy}>{t("g.common.add")}</button>
            {noteErr && <p style={{ color: "#fca5a5", fontSize: 11, margin: 0 }}>{noteErr}</p>}
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            {notes.length === 0 && <p style={{ fontSize: 11, opacity: 0.6, margin: 0 }}>{t("g.privacy.empty")}</p>}
            {notes.map((n) => {
              const rid = Number(n.id);
              const rev = revealed[rid];
              return (
                <div key={String(n.id)} style={{ border: "1px solid rgba(255,255,255,.1)", borderRadius: 6, padding: "6px 8px", fontSize: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 6 }}>
                    <strong style={{ opacity: 0.85 }}>{rev ? rev.split("\n\n")[0] : t("g.common.locked")}</strong>
                    <span style={{ display: "flex", gap: 4 }}>
                      <button type="button" className={btnCls} disabled={busy || !pass} onClick={() => void reveal(n)}>{t("g.common.unlock")}</button>
                      <button type="button" className={btnCls} disabled={busy} onClick={() => void delNote(rid)}>{t("g.common.delete")}</button>
                    </span>
                  </div>
                  {rev ? (
                    <pre style={{ whiteSpace: "pre-wrap", margin: "4px 0 0", fontSize: 11 }}>{rev}</pre>
                  ) : (
                    <p style={{ fontSize: 10, opacity: 0.55, margin: "4px 0 0" }}>{t("g.privacy.reveal_hint")}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
      {/* ── Hassas işlem izinleri (madde 25) ── */}
      {tab === "permissions" && (
        <div style={{ display: "grid", gap: 6 }}>
          <p style={{ fontSize: 11, opacity: 0.75, margin: 0 }}>{t("g.permissions.desc")}</p>
          {known.map((key) => (
            <label key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6, fontSize: 12 }}>
              <code style={{ fontSize: 11 }}>{key}</code>
              <input
                type="checkbox"
                checked={Boolean(perms[key])}
                disabled={busy}
                onChange={(e) => void togglePerm(key, e.target.checked)}
              />
            </label>
          ))}
          {known.length === 0 && <p style={{ fontSize: 11, opacity: 0.6, margin: 0 }}>{t("g.privacy.empty")}</p>}
        </div>
      )}

      {/* ── Güvenlik denetim kaydı (madde 25) ── */}
      {tab === "audit" && (
        <div style={{ display: "grid", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button type="button" className={btnCls} onClick={downloadAudit} disabled={busy}>{t("g.audit.download")}</button>
          </div>
          {entries.length === 0 && <p style={{ fontSize: 11, opacity: 0.6, margin: 0 }}>{t("g.audit.empty")}</p>}
          {entries.map((e, i) => (
            <div key={String(e.id ?? i)} style={{ fontSize: 11, borderBottom: "1px solid rgba(255,255,255,.06)", paddingBottom: 4 }}>
              <span style={{ opacity: 0.6 }}>{e.ts ?? ""} </span>
              <strong>{e.action ?? ""}</strong>
              {e.detail ? <span style={{ opacity: 0.75 }}> — {e.detail}</span> : null}
            </div>
          ))}
        </div>
      )}
      {/* ── Sağlık ve odak (madde 27) ── */}
      {tab === "wellness" && (
        <div style={{ display: "grid", gap: 8 }}>
          <p style={{ fontSize: 12, margin: 0 }}>{t("g.wellness.mood_q")}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {moodKeys.map(([val, key]) => (
              <button
                key={val}
                type="button"
                className={btnCls}
                disabled={busy}
                style={{ opacity: wb.last_mood === val ? 1 : 0.7 }}
                onClick={() => void setMood(val)}
              >
                {t(key)}
              </button>
            ))}
          </div>

          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
            <input type="checkbox" checked={focusMode} onChange={(e) => setFocusMode(e.target.checked)} />
            <span>{t("g.wellness.focus")}</span>
          </label>

          <label style={{ fontSize: 12 }}>
            {t("g.wellness.break_min")}
            <input className={inputCls} type="number" min={0} max={240} value={breakMin} onChange={(e) => setBreakMin(e.target.value)} />
          </label>
          <label style={{ fontSize: 12 }}>
            {t("g.wellness.daily")}
            <input className={inputCls} type="number" min={0} max={1440} value={dailyMin} onChange={(e) => setDailyMin(e.target.value)} />
          </label>

          {typeof wb.used_today === "number" && (
            <p style={{ fontSize: 11, opacity: 0.7, margin: 0 }}>
              {t("g.wellness.used")}: {String(wb.used_today)}
            </p>
          )}

          <button type="button" className={btnCls} onClick={saveWellness} disabled={busy}>{t("g.common.save")}</button>
        </div>
      )}

      {/* ── Erişilebilirlik + kişilik (madde 26) ── */}
      {tab === "a11y" && (
        <div style={{ display: "grid", gap: 8 }}>
          <label style={{ fontSize: 12 }}>
            {t("g.a11y.font")}
            <select className={inputCls} value={String(fontScale)} onChange={(e) => setFontScale(Number(e.target.value))}>
              <option value="0.9">{t("g.a11y.fs_sm")}</option>
              <option value="1">{t("g.a11y.fs_md")}</option>
              <option value="1.15">{t("g.a11y.fs_lg")}</option>
            </select>
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
            <input type="checkbox" checked={dyslexic} onChange={(e) => setDyslexic(e.target.checked)} />
            <span>{t("g.a11y.dyslexic")}</span>
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
            <input type="checkbox" checked={contrast} onChange={(e) => setContrast(e.target.checked)} />
            <span>{t("g.a11y.contrast")}</span>
          </label>

          <label style={{ fontSize: 12 }}>
            {t("g.a11y.widgets")}
            <input className={inputCls} value={widgets} onChange={(e) => setWidgets(e.target.value)} placeholder="weather, files, agent" />
          </label>

          <label style={{ fontSize: 12 }}>
            {t("g.a11y.persona")}
            <input className={inputCls} value={personaName} onChange={(e) => setPersonaName(e.target.value)} placeholder={t("g.a11y.persona_hint")} />
          </label>
          {styles.length > 0 && (
            <label style={{ fontSize: 12 }}>
              style
              <select className={inputCls} value={personaStyle} onChange={(e) => setPersonaStyle(e.target.value)}>
                <option value="">—</option>
                {styles.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
          )}

          <button type="button" className={btnCls} onClick={saveA11y} disabled={busy}>{t("g.common.save")}</button>
        </div>
      )}
    </Card>
  );
}