import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";

/** Redirect to /login if not authenticated; otherwise render nested routes. */
export function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
