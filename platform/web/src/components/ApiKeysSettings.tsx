/**
 * ApiKeysSettings — Özellik 5B: kullanıcı bazlı API anahtarları.
 * Değerler DB'de Fernet şifreli; hiçbir zaman geri gösterilmez.
 * Misafir: sekme kilitli ("Bu özellik için giriş yapmalısınız").
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuthUser } from "../hooks/useAuth";

interface KeyRow {
  key_name: string;
  has_value: boolean;
  updated_at: string | null;
}

/** Mega prompt 5B.9 + F18 listesi — etiket bilgisiyle. */
const KEY_DEFS: { name: string; label: string }[] = [
  { name: "GEMINI_API_KEY", label: "Google Gemini (Özellik 18 önceliği)" },
  { name: "DEEPSEEK_API_KEY", label: "DeepSeek R1" },
  { name: "GROQ_API_KEY", label: "Groq LLM" },
  { name: "OPENAI_API_KEY", label: "OpenAI" },
  { name: "ANTHROPIC_API_KEY", label: "Anthropic Claude" },
  { name: "SERPAPI_KEY", label: "Web Arama — SerpAPI (isteğe bağlı)" },
  { name: "OWM_API_KEY", label: "OpenWeatherMap" },
  { name: "HA_URL", label: "Home Assistant URL" },
  { name: "HA_TOKEN", label: "Home Assistant Token" },
  { name: "CALLMEBOT_PHONE", label: "WhatsApp — CallMeBot Telefon" },
  { name: "CALLMEBOT_KEY", label: "WhatsApp — CallMeBot Anahtar" },
  { name: "RELAY_URL", label: "Relay Sunucu URL" },
  { name: "RELAY_TOKEN", label: "Relay Token" },
  { name: "WOL_NODE_URL", label: "WoL Node URL" },
  { name: "WOL_NODE_SECRET", label: "WoL Node Secret" },
];

export default function ApiKeysSettings({ user }: { user: AuthUser | null }) {
  const [keys, setKeys] = useState<Record<string, KeyRow>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busyName, setBusyName] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    try {
      const rows = (await api.listApiKeys()).keys;
      setKeys(Object.fromEntries(rows.map((r) => [r.key_name, r])));
    } catch {
      /* offline veya oturum yok */
    }
  }, []);

  useEffect(() => {
    if (user) void refresh();
  }, [user, refresh]);

  if (!user) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-center text-xs text-amber-200">
        🔒 Bu özellik için giriş yapmalısınız. API anahtarlarınız hesabınıza
        şifreli olarak kaydedilir.
      </div>
    );
  }

  const save = async (keyName: string) => {
    const value = (drafts[keyName] ?? "").trim();
    if (!value) return;
    setBusyName(keyName);
    try {
      await api.setApiKey(keyName, value);
      setDrafts((d) => ({ ...d, [keyName]: "" }));
      setFeedback((f) => ({ ...f, [keyName]: "✅ Kaydedildi" }));
      await refresh();
    } catch (e) {
      setFeedback((f) => ({
        ...f,
        [keyName]: e instanceof Error ? `⚠ ${e.message}` : "⚠ Kaydedilemedi",
      }));
    } finally {
      setBusyName(null);
      setTimeout(() => setFeedback((f) => ({ ...f, [keyName]: "" })), 3000);
    }
  };

  const test = async (keyName: string) => {
    setBusyName(keyName);
    try {
      const resp = await api.testApiKey(keyName);
      setFeedback((f) => ({
        ...f,
        [keyName]: resp.ok ? "✅ Geçerli" : `⚠ ${resp.detail || "geçersiz"}`,
      }));
    } catch (e) {
      setFeedback((f) => ({
        ...f,
        [keyName]: e instanceof Error ? `⚠ ${e.message}` : "⚠ Test edilemedi",
      }));
    } finally {
      setBusyName(null);
      setTimeout(() => setFeedback((f) => ({ ...f, [keyName]: "" })), 4000);
    }
  };

  const remove = async (keyName: string) => {
    setBusyName(keyName);
    try {
      await api.deleteApiKey(keyName);
      await refresh();
    } catch {
      /* offline */
    } finally {
      setBusyName(null);
    }
  };

  return (
    <div className="space-y-2">
      <p className="text-[10px] text-slate-500">
        Kullanıcı anahtarları .env değerlerinden ÖNCE kullanılır (öncelik:
        hesap, sonra .env). Değerler Fernet ile şifreli saklanır; bir kez
        kaydettikten sonra tekrar gösterilmez.
      </p>
      {KEY_DEFS.map(({ name, label }) => {
        const row = keys[name];
        return (
          <div key={name} className="rounded-lg border p-2" style={{ borderColor: "var(--border)" }}>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[10px] font-semibold text-slate-300">{label}</span>
              <span className="text-[9px] text-slate-500">
                {row?.has_value
                  ? `kayıtlı${row.updated_at ? ` · ${row.updated_at.slice(0, 16).replace("T", " ")}` : ""}`
                  : "boş"}
              </span>
            </div>
            <div className="flex gap-1.5">
              <input
                type="password"
                value={drafts[name] ?? ""}
                onChange={(e) => setDrafts((d) => ({ ...d, [name]: e.target.value }))}
                placeholder={row?.has_value ? "•••••••• (değiştirmek için yazın)" : name}
                autoComplete="off"
                className="min-h-[40px] flex-1 rounded-md border bg-black/30 px-2 py-1.5 text-[11px] text-slate-200 outline-none placeholder:text-slate-600"
                style={{ borderColor: "var(--border)" }}
              />
              <button
                type="button"
                onClick={() => void save(name)}
                disabled={busyName === name || !(drafts[name] ?? "").trim()}
                className="btn-accent min-h-[40px] rounded-md px-2.5 text-[10px] font-semibold"
              >
                Kaydet
              </button>
              <button
                type="button"
                onClick={() => void test(name)}
                disabled={busyName === name}
                className="min-h-[40px] rounded-md border px-2 text-[10px] text-slate-300 hover:bg-white/5"
                style={{ borderColor: "var(--border)" }}
                title="Gerçek API'ye ping at"
              >
                Test
              </button>
              {row?.has_value && (
                <button
                  type="button"
                  onClick={() => void remove(name)}
                  disabled={busyName === name}
                  className="min-h-[40px] rounded-md px-1.5 text-[10px] text-slate-500 hover:text-rose-400"
                  title="Anahtarı sil"
                >
                  ✕
                </button>
              )}
            </div>
            {feedback[name] && (
              <p className="mt-0.5 text-[9px] text-slate-400">{feedback[name]}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
