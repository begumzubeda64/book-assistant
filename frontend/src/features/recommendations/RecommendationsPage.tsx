import { EmptyState } from "@/components/states";

export function RecommendationsPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold">Recommendations</h1>
      <p className="mt-1 text-slate-500">
        Book suggestions based on your reading activity and saved concepts.
      </p>
      <div className="mt-4">
        <EmptyState title="Recommendations are coming soon">
          This feature is being built. It will suggest books using transparent
          signals (category and author similarity, saved concepts, and your
          started and completed books), each with a short reason.
        </EmptyState>
      </div>
    </div>
  );
}
