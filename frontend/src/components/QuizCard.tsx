import { useState } from "react";
import { gradeAnswer, makeQuiz, type Grade, type Quiz } from "../api";

export default function QuizCard({
  sessionId,
  onGraded,
}: {
  sessionId: string;
  onGraded: () => void;
}) {
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [idx, setIdx] = useState(0);
  const [chosen, setChosen] = useState<number | null>(null);
  const [grade, setGrade] = useState<Grade | null>(null);
  const [loading, setLoading] = useState(false);
  const [topic, setTopic] = useState("");

  async function start() {
    setLoading(true);
    const q = await makeQuiz(sessionId, topic, 4);
    setQuiz(q);
    setIdx(0);
    setChosen(null);
    setGrade(null);
    setLoading(false);
  }

  async function submit() {
    if (chosen == null || !quiz) return;
    const g = await gradeAnswer(sessionId, quiz.questions[idx].id, chosen);
    setGrade(g);
    onGraded();
  }

  function next() {
    if (!quiz) return;
    if (idx + 1 < quiz.questions.length) {
      setIdx(idx + 1);
      setChosen(null);
      setGrade(null);
    } else {
      setQuiz(null);
    }
  }

  const q = quiz?.questions[idx];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Get quizzed</h3>
        {quiz && (
          <span className="text-xs text-gray-400">
            {idx + 1} / {quiz.questions.length}
          </span>
        )}
      </div>

      {!quiz && (
        <div className="flex gap-2">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Topic (optional)"
            className="flex-1 rounded-lg border px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <button
            onClick={start}
            disabled={loading}
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {loading ? "…" : "Start quiz"}
          </button>
        </div>
      )}

      {q && (
        <div>
          <p className="mb-1 text-[11px] uppercase tracking-wide text-indigo-500">
            {q.concept} · {q.difficulty}
          </p>
          <p className="mb-3 text-sm font-medium">{q.prompt}</p>
          <div className="space-y-2">
            {q.choices.map((choice, i) => (
              <label
                key={i}
                className={
                  "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm " +
                  (chosen === i ? "border-accent bg-indigo-50" : "border-gray-200") +
                  (grade
                    ? ""
                    : " hover:border-accent")
                }
              >
                <input
                  type="radio"
                  name={q.id}
                  checked={chosen === i}
                  disabled={!!grade}
                  onChange={() => setChosen(i)}
                />
                {choice}
              </label>
            ))}
          </div>

          {!grade ? (
            <button
              onClick={submit}
              disabled={chosen == null}
              className="mt-3 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Submit answer
            </button>
          ) : (
            <div className="mt-3">
              <div
                className={
                  "rounded-lg p-3 text-sm " +
                  (grade.correct
                    ? "bg-green-50 text-green-800"
                    : "bg-red-50 text-red-800")
                }
              >
                <p className="font-medium">
                  {grade.correct ? "✓ Correct" : "✗ Not quite"}
                  {grade.misconception_tag && (
                    <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 text-[11px]">
                      {grade.misconception_tag}
                    </span>
                  )}
                </p>
                <p className="mt-1">{grade.feedback}</p>
                {grade.followup_prompt && (
                  <p className="mt-2 italic">Follow-up: {grade.followup_prompt}</p>
                )}
              </div>
              <button
                onClick={next}
                className="mt-3 rounded-lg border border-accent px-3 py-2 text-sm font-medium text-accent"
              >
                {idx + 1 < (quiz?.questions.length ?? 0) ? "Next question" : "Finish"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
