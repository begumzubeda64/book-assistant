import { RouterProvider } from "react-router-dom";

import { router } from "@/app/router";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthProvider } from "@/features/auth/authContext";

export function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ErrorBoundary>
  );
}
