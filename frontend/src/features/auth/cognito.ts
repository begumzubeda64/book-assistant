// Cognito Hosted UI OIDC flow (authorization code + PKCE).
//
// Configured via env (set when VITE_AUTH_MODE=cognito):
//   VITE_COGNITO_DOMAIN     e.g. https://book-companion-prod.auth.eu-central-1.amazoncognito.com
//   VITE_COGNITO_CLIENT_ID  the app client id
//   VITE_COGNITO_REDIRECT   e.g. https://app.example.com/auth/callback
//
// Tokens are kept in sessionStorage. This is a public SPA client (no secret),
// so PKCE protects the code exchange.

interface Tokens {
  access_token: string;
  id_token: string;
  refresh_token?: string;
  expires_at: number; // epoch ms
}

const DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN ?? "";
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID ?? "";
const REDIRECT_URI = import.meta.env.VITE_COGNITO_REDIRECT ?? "";
const SCOPE = "openid email profile";

const TOKENS_KEY = "bc:cognito:tokens";
const VERIFIER_KEY = "bc:cognito:pkce_verifier";

function base64UrlEncode(bytes: Uint8Array): string {
  let str = "";
  for (const b of bytes) str += String.fromCharCode(b);
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function sha256(input: string): Promise<Uint8Array> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return new Uint8Array(digest);
}

function randomString(length = 64): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes).slice(0, length);
}

/** Begin sign-in: redirect to the Cognito Hosted UI with a PKCE challenge. */
export async function beginSignIn(): Promise<void> {
  const verifier = randomString();
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  const challenge = base64UrlEncode(await sha256(verifier));
  const params = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    scope: SCOPE,
    code_challenge_method: "S256",
    code_challenge: challenge,
  });
  window.location.assign(`${DOMAIN}/oauth2/authorize?${params}`);
}

/** Handle the /auth/callback redirect: exchange the code for tokens. */
export async function handleCallback(code: string): Promise<void> {
  const verifier = sessionStorage.getItem(VERIFIER_KEY) ?? "";
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
    code_verifier: verifier,
  });
  const resp = await fetch(`${DOMAIN}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!resp.ok) {
    throw new Error("Token exchange failed");
  }
  const data = (await resp.json()) as {
    access_token: string;
    id_token: string;
    refresh_token?: string;
    expires_in: number;
  };
  const tokens: Tokens = {
    access_token: data.access_token,
    id_token: data.id_token,
    refresh_token: data.refresh_token,
    expires_at: Date.now() + data.expires_in * 1000,
  };
  sessionStorage.setItem(TOKENS_KEY, JSON.stringify(tokens));
  sessionStorage.removeItem(VERIFIER_KEY);
}

export function getStoredTokens(): Tokens | null {
  const raw = sessionStorage.getItem(TOKENS_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    return null;
  }
}

/** Current access token, or null if absent/expired. */
export function getAccessToken(): string | null {
  const tokens = getStoredTokens();
  if (!tokens) return null;
  if (Date.now() >= tokens.expires_at) return null;
  return tokens.access_token;
}

/** Decode the id token to a minimal user profile (sub + email). */
export function getUserFromIdToken(): { userId: string; email?: string } | null {
  const tokens = getStoredTokens();
  if (!tokens) return null;
  try {
    const payload = JSON.parse(
      atob(tokens.id_token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as { sub: string; email?: string };
    return { userId: payload.sub, email: payload.email };
  } catch {
    return null;
  }
}

export function clearTokens(): void {
  sessionStorage.removeItem(TOKENS_KEY);
}

/** Redirect to the Hosted UI logout endpoint. */
export function hostedLogout(): void {
  clearTokens();
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: window.location.origin,
  });
  window.location.assign(`${DOMAIN}/logout?${params}`);
}
