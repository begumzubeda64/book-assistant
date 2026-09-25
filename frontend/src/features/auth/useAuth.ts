import { createContext, useContext } from "react";

export type AuthMode = "local" | "cognito";

export interface AuthUser {
  userId: string;
  email?: string;
}

export interface AuthState {
  mode: AuthMode;
  user: AuthUser | null;
  isAuthenticated: boolean;
  signIn: () => Promise<void>;
  signOut: () => void;
  /** Returns a bearer token, or null in local-dev mode. */
  getToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
