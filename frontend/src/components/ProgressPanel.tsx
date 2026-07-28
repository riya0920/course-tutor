import { useEffect } from "react";
import { type ProgressReport } from "../api";

export default function ProgressPanel({
  report,
  refresh,
}: {
  report: ProgressReport | null;
  refresh: () => void;
}) {
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Mastery</h3>
        {report && (
          <span className="text-xs text-gray-400">
            {report.total_correct}/{report.total_attempts} correct
          </span>
        )}
      </div>
      {(!report || report.concepts.length === 0) && (
        <p className="text-xs text-gray-400">
          Answer quiz questions to build your mastery map.
        </p>
      )}
      <div className="space-y-3">
        {report?.concepts.map((c) => {
          const rate = c.attempts ? c.correct / c.attempts : 0;
          return (
            <div key={c.concept}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="font-medium">{c.concept}</span>
                <span className="text-gray-400">
                  {c.correct}/{c.attempts}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.round(rate * 100)}%`,
                    background:
                      rate >= 0.7 ? "#16a34a" : rate >= 0.4 ? "#d97706" : "#dc2626",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
