/** Giriş kapısı: misafir mi, hesap mı? (Prompt 1 + 2).
 *
 * - PC (loopback): giriş zorunlu değil — doğrudan uygulama açılır.
 * - Uzak cihaz, eşleşmiş (device_token var): "Giriş yap" veya "Misafir" seçer.
 * - Uzak cihaz, eşleşmemiş: kendi PairingGate'i (QR/PIN) devreye girer.
 *
 * Misafir seçimi oturumluk (sessionStorage) tutulur; web misafir modunda
 * X-Client-ID başlığı GÖNDERİLMEZ, böylece backend owner='guest:*' üretir
 * (kalıcılık guard'ının ön koşulu).
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { authToken, deviceToken } from "../api/client";
import { t } from "../i18n";
import AuthScreen from "./AuthScreen";

const LOOPBACK = ["localhost", "127.0.0.1", "[::1]", "::1"];
const GUEST_KEY = "jarvis.guest";

export const isGuestMode = () => {
  try {
    return sessionStorage.getItem(GUEST_KEY) === "1";
  } catch {
    return false;
  }
};

export const clearGuestMode = () => {
  try {
    sessionStorage.removeItem(GUEST_KEY);
  } catch {
    /* yok */
  }
};

const setGuestMode = () => {
  try {
    sessionStorage.setItem(GUEST_KEY, "1");
  } catch {
    /* yok */
  }
};

export default function LoginGate({ children }: { children: ReactNode }) {
  const [guest, setGuest] = useState(isGuestMode());
  const [signedIn, setSignedIn] = useState(authToken.isLoggedIn());
  const isPC = LOOPBACK.includes(location.hostname);

  useEffect(() => {
    const onExpired = () => setSignedIn(false);
    window.addEventListener("jarvis:auth-expired", onExpired);
    return () => window.removeEventListener("jarvis:auth-expired", onExpired);
  }, []);

  if (isPC || guest) return <>{children}</>;
  // Uzak cihaz, eşleşmiş (device_token var) → giriş / misafir seçimi.
  if (!deviceToken.get()) return <>{children}</>;

  if (!signedIn) {
    return (
      <AuthScreen
        onSignedIn={() => setSignedIn(true)}
        onGuest={() => {
          setGuestMode();
          setGuest(true);
        }}
      />
    );
  }

  return (
    <>
      {guest && (
        <div
          className="sticky top-0 z-40 border-b px-3 py-1.5 text-center text-[11px] font-medium text-amber-200"
          style={{ borderColor: "var(--border)", background: "rgb(80 53 15 / 0.9)" }}
        >
          {t("guest.banner")}
        </div>
      )}
      {children}
    </>
  );
}
