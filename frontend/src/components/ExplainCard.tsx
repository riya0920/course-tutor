import { useState } from "react";
import { explainConcept, type Explanation } from "../api";

// Demoes the fine-tuning component: the same concept explained by the base
// model vs. the fine-tuned model (restate -> explain -> example -> check).
export default function ExplainCard({ sessionId }: { sessionId: string }) {
  const [concept, setConcept] = useState("");
  const [model, setModel] = useState<"base" | "tuned">("base");
  const [result, setResult] = useState<Explanation | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    if (!concept.trim()) return;
    setLoading(true);
    setResult(await explainConcept(sessionId, concept.trim(), model));
    setLoading(false);
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Explain a concept</h3>
        <div className="flex overflow-hidden rounded-lg border text-xs">
          {(["base", "tuned"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setModel(m)}
              className={
                "px-2 py-1 " +
                (model === m ? "bg-accent text-white" : "bg-white text-gray-600")
              }
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        <input
          value={concept}
          onChange={(e) => setConcept(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="e.g. gradient descent"
          className="flex-1 rounded-lg border px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          onClick={run}
          disabled={loading}
          className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "…" : "Explain"}
        </button>
      </div>
      {result && (
        <div className="mt-3 rounded-lg bg-gray-50 p-3 text-sm">
          <p className="mb-1 text-[11px] uppercase tracking-wide text-indigo-500">
            model: {result.model}
          </p>
          <p className="whitespace-pre-wrap">{result.explanation}</p>
        </div>
      )}
    </div>
  );
}
