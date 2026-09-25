import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { setTokenProvider } from "@/services/api";

import { AuthContext, type AuthMode, type AuthState, type AuthUser } from "./useAuth";

/**
 * Authentication provider.
 *
 * Local-dev-first: when VITE_AUTH_MODE is "local" (the default), signing in is a
 * no-op that marks the session authenticated and relies on the backend's
 * local-dev auth bypass (no bearer token required). The real Cognito flow slots
 * in behind VITE_AUTH_MODE="cognito" later, providing a real access token via
 * `getToken`.
 */

const AUTH_MODE = (import.meta.env.VITE_AUTH_MODE ?? "local") as AuthMode;
const LOCAL_DEV_USER: AuthUser = { userId: "local-dev-user", email: "dev@local" };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(
    AUTH_MODE === "local" ? LOCAL_DEV_USER : null,
  );

  const signIn = useCallback(async () => {
    if (AUTH_MODE === "local") {
      setUser(LOCAL_DEV_USER);
      return;
    }
    // TODO(auth): redirect to the Cognito Hosted UI / exchange code for tokens.
    throw new Error("Cognito sign-in is not configured yet");
  }, []);

  const signOut = useCallback(() => {
    setUser(null);
  }, []);

  const getToken = useCallback(async () => {
    if (AUTH_MODE === "local") return null;
    // TODO(auth): return the current Cognito access token.
    return null;
  }, []);

  useEffect(() => {
    setTokenProvider(getToken);
  }, [getToken]);

  const value = useMemo<AuthState>(
    () => ({
      mode: AUTH_MODE,
      user,
      isAuthenticated: user !== null,
      signIn,
      signOut,
      getToken,
    }),
    [user, signIn, signOut, getToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
