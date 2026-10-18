import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { setTokenProvider, setUnauthorizedHandler } from "@/services/api";

import {
  beginSignIn,
  clearTokens,
  getAccessToken,
  getUserFromIdToken,
  hostedLogout,
} from "./cognito";
import { AuthContext, type AuthMode, type AuthState, type AuthUser } from "./useAuth";

/**
 * Authentication provider.
 *
 * - VITE_AUTH_MODE="local" (default): signing in is a no-op; the backend's
 *   local-dev bypass authenticates requests (no bearer token).
 * - VITE_AUTH_MODE="cognito": real Cognito Hosted UI (authorization code + PKCE,
 *   see cognito.ts). Access tokens are sent as the bearer credential.
 */

const AUTH_MODE = (import.meta.env.VITE_AUTH_MODE ?? "local") as AuthMode;
const LOCAL_DEV_USER: AuthUser = { userId: "local-dev-user", email: "dev@local" };

function initialUser(): AuthUser | null {
  if (AUTH_MODE === "local") return LOCAL_DEV_USER;
  // Cognito: restore from a valid stored session if present.
  return getAccessToken() ? getUserFromIdToken() : null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(initialUser);

  const signIn = useCallback(async () => {
    if (AUTH_MODE === "local") {
      setUser(LOCAL_DEV_USER);
      return;
    }
    await beginSignIn(); // redirects to the Hosted UI
  }, []);

  const signOut = useCallback(() => {
    if (AUTH_MODE === "cognito") {
      hostedLogout(); // clears tokens + redirects to the Hosted UI logout
      return;
    }
    setUser(null);
  }, []);

  const getToken = useCallback(async () => {
    if (AUTH_MODE === "local") return null;
    return getAccessToken();
  }, []);

  // Keep the user in sync with Cognito session state (e.g. after callback).
  const refreshUser = useCallback(() => {
    if (AUTH_MODE === "cognito") {
      setUser(getAccessToken() ? getUserFromIdToken() : null);
    }
  }, []);

  useEffect(() => {
    setTokenProvider(getToken);
  }, [getToken]);

  // Treat an expired/invalid session as logged out so the app routes back to
  // the login screen instead of showing a stale nav bar with a dead session.
  useEffect(() => {
    if (AUTH_MODE !== "cognito") return;

    // Clear the local session (no Hosted UI round trip) and drop to logged-out.
    // The SPA's ProtectedRoute then sends the user to /login.
    const handleUnauthorized = () => {
      clearTokens();
      setUser(null);
    };
    setUnauthorizedHandler(handleUnauthorized);

    // Re-check token validity on mount and whenever the tab regains focus, so
    // an expiry that happened while away is reflected without a failed request.
    const syncFromToken = () => {
      setUser(getAccessToken() ? getUserFromIdToken() : null);
    };
    syncFromToken();
    const onVisible = () => {
      if (document.visibilityState === "visible") syncFromToken();
    };
    window.addEventListener("focus", syncFromToken);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      setUnauthorizedHandler(() => {});
      window.removeEventListener("focus", syncFromToken);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      mode: AUTH_MODE,
      user,
      isAuthenticated: user !== null,
      signIn,
      signOut,
      getToken,
      refreshUser,
    }),
    [user, signIn, signOut, getToken, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
