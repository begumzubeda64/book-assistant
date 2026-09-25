import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";

const NAV = [
  { to: "/", label: "Discover", end: true },
  { to: "/library", label: "My Library" },
  { to: "/recommendations", label: "Recommendations" },
];

export function Layout() {
  const { user, signOut, mode } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-8">
            <NavLink to="/" className="text-lg font-semibold">
              Book Companion
            </NavLink>
            <nav className="flex gap-4 text-sm">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    isActive
                      ? "font-medium text-slate-900"
                      : "text-slate-500 hover:text-slate-800"
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {mode === "local" && (
              <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                local dev
              </span>
            )}
            <span className="text-slate-500">{user?.email ?? user?.userId}</span>
            <button
              onClick={signOut}
              className="rounded border border-slate-300 px-2 py-1 text-slate-600 hover:bg-slate-100"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
