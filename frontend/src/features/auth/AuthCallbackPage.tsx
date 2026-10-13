import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ErrorState, Spinner } from "@/components/states";
import { handleCallback } from "@/features/auth/cognito";
import { useAuth } from "@/features/auth/useAuth";

/** Handles the Cognito Hosted UI redirect: exchanges the code, then continues. */
export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;

    const code = params.get("code");
    const authError = params.get("error");
    if (authError) {
      setError(params.get("error_description") ?? authError);
      return;
    }
    if (!code) {
      setError("Missing authorization code");
      return;
    }
    handleCallback(code)
      .then(() => {
        refreshUser();
        navigate("/", { replace: true });
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Sign-in failed"),
      );
  }, [params, navigate, refreshUser]);

  if (error) return <ErrorState message={error} />;
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner label="Completing sign-in…" />
    </div>
  );
}
