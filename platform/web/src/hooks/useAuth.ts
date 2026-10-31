/**
 * useAuth — Özellik 5: oturum yönetimi hook'u (kullanıcı adı akışı dahil).
 *
 * Tokenlar localStorage'da (client.authToken); login/register/refresh/logout
 * uçları client.ts'te. Misafir modu LoginGate ile koordineli (sessionStorage).
 */
import { useCallback, useEffect, useState } from "react";
import { api, authToken } from "../api/client";
import { isGuestMode } from "../components/LoginGate";

export interface AuthUser {
  user_id: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  local?: boolean;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user_id: string;
  username?: string;
  first_name?: string;
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    if (!authToken.isLoggedIn()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.authMe();
      setUser(me as AuthUser);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  /** Özellik 5A: kullanıcı adı + şifre ile giriş. */
  const loginWithUsername = useCallback(
    async (username: string, password: string): Promise<AuthUser> => {
      const resp = (await api.authLoginUsername(username, password)) as AuthResponse;
      authToken.set(resp.access_token, resp.refresh_token);
      const me = {
        user_id: resp.user_id,
        username: resp.username,
        first_name: resp.first_name,
      };
      setUser(me);
      return me;
    },
    []
  );

  /** Özellik 5A: kullanıcı adı + ad/soyad + şifre ile kayıt. */
  const registerWithUsername = useCallback(
    async (payload: {
      username: string;
      first_name: string;
      last_name: string;
      password: string;
      password_repeat: string;
    }): Promise<AuthUser> => {
      const resp = (await api.authRegisterUsername(payload)) as AuthResponse;
      authToken.set(resp.access_token, resp.refresh_token);
      const me = {
        user_id: resp.user_id,
        username: resp.username,
        first_name: resp.first_name,
      };
      setUser(me);
      return me;
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await api.authLogout();
    } catch {
      /* sunucu erişilemezse bile yerel oturum kapanır */
    }
    authToken.clear();
    setUser(null);
  }, []);

  return {
    user,
    loading,
    isLoggedIn: !!user || authToken.isLoggedIn(),
    isGuest: isGuestMode(),
    loginWithUsername,
    registerWithUsername,
    logout,
    refreshMe,
  };
}
