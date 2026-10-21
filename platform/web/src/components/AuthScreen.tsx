/** Giriş / Kayıt / Şifre sıfırlama ekranı (Prompt 1).
 *
 * PC'de (loopback) giriş zorunlu değildir; misafir modunda uzak cihazlar da
 * bu ekranı atlayabilir (davranış Prompt 2'de tamamlanacak).
 * Tokenlar localStorage'da saklanır (bkz. api/client.ts gerekçesi).
 */
import { useState } from "react";
import { api, ApiError, authToken } from "../api/client";
import { t } from "../i18n";

export type AuthMode = "login" | "register" | "reset";

interface Props {
  /** Sunucuda auth yapılandırılmamışsa (503) uyarı gösterilir. */
  unavailable?: boolean;
  onSignedIn?: () => void;
  onGuest: () => void;
}

const inputCls =
  "w-full rounded-lg border bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-slate-500 focus:border-slate-400/50";
const inputStyle = { borderColor: "var(--border)" };

export default function AuthScreen({ unavailable, onSignedIn, onGuest }: Props) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [password, setPassword] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const fail = (e: unknown) => {
    if (e instanceof ApiError) {
      setError(e.status === 429 ? t("auth.rate_limited") : e.message);
    } else {
      setError(e instanceof Error ? e.message : t("auth.failed"));
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === "register") {
        const pair = await api.authRegister({
          first_name: firstName,
          last_name: lastName,
          birth_date: birthDate,
          password,
          security_question: question,
          security_answer: answer,
        });
        authToken.set(pair.access_token, pair.refresh_token);
        onSignedIn?.();
      } else if (mode === "login") {
        const pair = await api.authLogin({
          first_name: firstName,
          last_name: lastName,
          password,
        });
        authToken.set(pair.access_token, pair.refresh_token);
        onSignedIn?.();
      } else {
        await api.authReset({
          first_name: firstName,
          last_name: lastName,
          birth_date: birthDate,
          security_answer: answer,
          new_password: newPassword,
        });
        setInfo(t("auth.reset_done"));
        setMode("login");
        setPassword("");
      }
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <form
        className="w-full max-w-sm rounded-2xl border p-6 shadow-2xl"
        style={{ borderColor: "var(--border-strong)", background: "rgb(8 10 18 / 0.9)" }}
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <h1 className="text-xl font-semibold tracking-widest text-slate-100">{t("auth.title")}</h1>
        <p className="mt-1 text-xs text-slate-400">{t("auth.subtitle")}</p>
        {unavailable && <p className="mt-2 text-xs text-amber-400">{t("auth.unavailable")}</p>}

        <div className="mt-4 space-y-2.5">
          <input
            className={inputCls}
            style={inputStyle}
            placeholder={t("auth.first_name")}
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            autoComplete="given-name"
            required
          />
          <input
            className={inputCls}
            style={inputStyle}
            placeholder={t("auth.last_name")}
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            autoComplete="family-name"
            required
          />
          {mode !== "login" && (
            <input
              className={inputCls}
              style={inputStyle}
              type="date"
              value={birthDate}
              onChange={(e) => setBirthDate(e.target.value)}
              required
            />
          )}
          {mode === "register" && (
            <>
              <input
                className={inputCls}
                style={inputStyle}
                placeholder={t("auth.security_question")}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                maxLength={200}
                required
              />
              <input
                className={inputCls}
                style={inputStyle}
                placeholder={t("auth.security_answer")}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                maxLength={120}
                required
              />
            </>
          )}
          {mode === "reset" && (
            <input
              className={inputCls}
              style={inputStyle}
              placeholder={t("auth.security_answer")}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              maxLength={120}
              required
            />
          )}
          {mode !== "reset" && (
            <input
              className={inputCls}
              style={inputStyle}
              type="password"
              placeholder={t("auth.password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
            />
          )}
          {mode === "reset" && (
            <>
              <p className="text-[11px] text-slate-500">{t("auth.reset_hint")}</p>
              <input
                className={inputCls}
                style={inputStyle}
                type="password"
                placeholder={t("auth.new_password")}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </>
          )}
        </div>

        {error && <p className="mt-3 text-xs text-rose-400">{error}</p>}
        {info && <p className="mt-3 text-xs text-emerald-400">{info}</p>}

        <button
          type="submit"
          disabled={busy}
          className="btn-accent mt-4 w-full rounded-lg py-2.5 text-sm font-semibold disabled:opacity-50"
        >
          {mode === "login" ? t("auth.login") : mode === "register" ? t("auth.register") : t("auth.reset_done")}
        </button>

        <div className="mt-3 flex items-center justify-between text-[11px]">
          <button
            type="button"
            className="text-slate-400 hover:text-slate-200"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
              setInfo(null);
            }}
          >
            {mode === "login" ? t("auth.register") : t("auth.back_to_login")}
          </button>
          <button
            type="button"
            className="text-slate-400 hover:text-slate-200"
            onClick={() => {
              setMode(mode === "reset" ? "login" : "reset");
              setError(null);
              setInfo(null);
            }}
          >
            {mode === "reset" ? t("auth.back_to_login") : t("auth.forgot")}
          </button>
        </div>

        <button
          type="button"
          onClick={onGuest}
          className="mt-4 w-full rounded-lg border px-3 py-2 text-xs text-slate-300 hover:bg-white/5"
          style={{ borderColor: "var(--border)" }}
        >
          {t("pair.continue_guest")}
        </button>
      </form>
    </div>
  );
}
