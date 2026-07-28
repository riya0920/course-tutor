import { useCallback, useState } from "react";
import ChatPane from "./components/ChatPane";
import ExplainCard from "./components/ExplainCard";
import ProgressPanel from "./components/ProgressPanel";
import QuizCard from "./components/QuizCard";
import UploadZone from "./components/UploadZone";
import { getProgress, type ProgressReport } from "./api";

export default function App() {
  // Default to the preloaded "sample" course so a stranger can try it with no
  // upload. Uploading a document switches to a fresh session.
  const [sessionId, setSessionId] = useState("sample");
  const [corpus, setCorpus] = useState("sample course (Intro to ML)");
  const [report, setReport] = useState<ProgressReport | null>(null);

  const refreshProgress = useCallback(async () => {
    setReport(await getProgress(sessionId));
  }, [sessionId]);

  function handleUploaded(sid: string, filename: string) {
    setSessionId(sid);
    setCorpus(filename);
    setReport(null);
  }

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-4 p-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">
            🎓 Course Tutor
          </h1>
          <p className="text-xs text-gray-500">
            Grounded RAG tutoring · adaptive quizzes · mastery tracking
          </p>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-xs text-gray-500 shadow-sm">
          corpus: <span className="font-medium text-ink">{corpus}</span>
        </span>
      </header>

      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[1fr_360px]">
        <div className="min-h-[420px]">
          <ChatPane sessionId={sessionId} />
        </div>
        <div className="space-y-4 overflow-y-auto">
          <UploadZone sessionId={sessionId} onUploaded={handleUploaded} />
          <QuizCard sessionId={sessionId} onGraded={refreshProgress} />
          <ProgressPanel report={report} refresh={refreshProgress} />
          <ExplainCard sessionId={sessionId} />
        </div>
      </div>
    </div>
  );
}
