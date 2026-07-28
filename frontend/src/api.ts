// API client. In dev, requests are same-origin and proxied to FastAPI (see
// vite.config.ts). In production set VITE_API_BASE to the deployed backend URL.
const BASE = import.meta.env.VITE_API_BASE ?? "";

export interface Citation {
  chunk_id: string;
  source: string;
  page: number | null;
  quote: string;
}

export interface ChatMeta {
  citations: Citation[];
  grounded: boolean;
  off_syllabus: boolean;
  cached_input_tokens: number;
  uncached_input_tokens: number;
  output_tokens: number;
  ttft_ms: number | null;
  model: string;
}

export interface QuizQuestion {
  id: string;
  concept: string;
  prompt: string;
  choices: string[];
  difficulty: string;
}

export interface Quiz {
  topic: string;
  questions: QuizQuestion[];
}

export interface Grade {
  question_id: string;
  correct: boolean;
  misconception_tag: string | null;
  feedback: string;
  followup_prompt: string | null;
}

export interface ConceptMastery {
  concept: string;
  attempts: number;
  correct: number;
}

export interface ProgressReport {
  session_id: string;
  concepts: ConceptMastery[];
  total_attempts: number;
  total_correct: number;
}

export async function uploadDocument(
  file: File,
  sessionId: string
): Promise<{ session_id: string; filename: string; chunks_indexed: number }> {
  const form = new FormData();
  form.append("file", file);
  form.append("session_id", sessionId);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  return res.json();
}

// Streams the tutor answer token-by-token. onToken fires per token; onMeta
// fires once with citations + telemetry at the end.
export async function streamChat(
  sessionId: string,
  message: string,
  onToken: (text: string) => void,
  onMeta: (meta: ChatMeta) => void
): Promise<void> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      const line = evt.trim();
      if (!line.startsWith("data:")) continue;
      const payload = JSON.parse(line.slice(5).trim());
      if (payload.type === "token") onToken(payload.text);
      else if (payload.type === "meta") onMeta(payload as ChatMeta);
    }
  }
}

export async function makeQuiz(
  sessionId: string,
  topic: string,
  n: number
): Promise<Quiz> {
  const res = await fetch(`${BASE}/quiz`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, topic, n }),
  });
  return res.json();
}

export async function gradeAnswer(
  sessionId: string,
  questionId: string,
  chosenIndex: number
): Promise<Grade> {
  const res = await fetch(`${BASE}/quiz/grade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      question_id: questionId,
      chosen_index: chosenIndex,
    }),
  });
  return res.json();
}

export async function getProgress(sessionId: string): Promise<ProgressReport> {
  const res = await fetch(`${BASE}/progress/${sessionId}`);
  return res.json();
}
