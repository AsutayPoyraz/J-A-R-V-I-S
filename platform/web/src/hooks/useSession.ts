/** Misafir modu: oturum bilgisi + yetenek yardımcıları (Prompt 2).
 *
 * `capabilities` backend'in /api/session yanıtından gelir; seçili misafir
 * modunda (sessionStorage + X-Client-ID gönderilmez) güvenli tarafa
 * (kapalı) düşülür.
 */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { isGuestMode } from "../components/LoginGate";

export type Capability = "chat" | "files" | "device_control" | "history" | "settings_write";

export interface SessionInfo {
  mode: "guest" | "user" | "local";
  capabilities: Record<Capability, boolean>;
}

const GUEST_CAPS: Record<Capability, boolean> = {
  chat: true,
  files: false,
  device_control: false,
  history: false,
  settings_write: false,
};

const LOCAL_CAPS: Record<Capability, boolean> = {
  chat: true,
  files: true,
  device_control: true,
  history: true,
  settings_write: true,
};

export function useSession(): SessionInfo & { can: (cap: Capability) => boolean } {
  const [session, setSession] = useState<SessionInfo>(() =>
    isGuestMode()
      ? { mode: "guest", capabilities: GUEST_CAPS }
      : { mode: "local", capabilities: LOCAL_CAPS }
  );

  useEffect(() => {
    if (isGuestMode()) return;
    let alive = true;
    api
      .session()
      .then((s) => alive && setSession(s))
      .catch(() => {
        /* çevrimdışı: mevcut varsayım korunur */
      });
    return () => {
      alive = false;
    };
  }, []);

  const capabilities = isGuestMode() ? GUEST_CAPS : session.capabilities;
  return {
    mode: isGuestMode() ? "guest" : session.mode,
    capabilities,
    can: (cap: Capability) => capabilities[cap] === true,
  };
}
