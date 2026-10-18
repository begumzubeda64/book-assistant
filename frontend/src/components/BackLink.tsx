import { Link } from "react-router-dom";

/**
 * A top-of-page back affordance with a leading arrow. Links to an explicit
 * destination (a list or menu) rather than relying on browser history, so the
 * target is predictable regardless of how the user arrived.
 */
export function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
    >
      <svg
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-4 w-4"
        aria-hidden="true"
      >
        <path d="M12 15l-5-5 5-5" />
      </svg>
      {label}
    </Link>
  );
}
