import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";

export function LoginPage() {
  const { signIn, mode, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) {
    navigate("/", { replace: true });
  }

  async function handleSignIn() {
    setError(null);
    try {
      await signIn();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold">Book Companion</h1>
        <p className="mt-2 text-sm text-slate-600">
          Read a book in 3, 5, or 10 minutes without losing its meaning.
        </p>

        {mode === "local" ? (
          <p className="mt-4 rounded bg-amber-50 p-3 text-xs text-amber-800">
            Local development mode. Sign in continues as a local dev user; the
            backend authenticates the request with its local bypass.
          </p>
        ) : (
          <p className="mt-4 text-xs text-slate-500">Sign in with your account.</p>
        )}

        {error && (
          <p className="mt-4 rounded bg-rose-50 p-3 text-sm text-rose-700">
            {error}
          </p>
        )}

        <button
          onClick={handleSignIn}
          className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800"
        >
          {mode === "local" ? "Continue as dev user" : "Sign in"}
        </button>
      </div>
    </div>
  );
}
