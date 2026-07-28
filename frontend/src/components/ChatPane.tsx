import { useRef, useState } from "react";
import { streamChat, type ChatMeta, type Citation } from "../api";

interface Turn {
  role: "user" | "assistant";
  text: string;
  meta?: ChatMeta;
}

export default function ChatPane({ sessionId }: { sessionId: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function send() {
    const message = input.trim();
    if (!message || streaming) return;
    setInput("");
    setTurns((t) => [...t, { role: "user", text: message }, { role: "assistant", text: "" }]);
    setStreaming(true);

    await streamChat(
      sessionId,
      message,
      (tok) =>
        setTurns((t) => {
          const next = [...t];
          next[next.length - 1] = {
            ...next[next.length - 1],
            text: next[next.length - 1].text + tok,
          };
          return next;
        }),
      (meta) =>
        setTurns((t) => {
          const next = [...t];
          next[next.length - 1] = { ...next[next.length - 1], meta };
          return next;
        })
    );
    setStreaming(false);
    setTimeout(() => scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight), 50);
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-gray-200 bg-white">
      <div className="border-b px-4 py-2 text-sm font-semibold">Learn</div>
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {turns.length === 0 && (
          <p className="text-sm text-gray-400">
            Ask a question about your uploaded material. Answers are grounded in the
            source with citations.
          </p>
        )}
        {turns.map((turn, i) => (
          <div key={i} className={turn.role === "user" ? "text-right" : ""}>
            <div
              className={
                "inline-block max-w-[85%] rounded-2xl px-3 py-2 text-sm " +
                (turn.role === "user"
                  ? "bg-accent text-white"
                  : "bg-gray-100 text-ink")
              }
            >
              {turn.text || <span className="opacity-50">…</span>}
            </div>
            {turn.meta && <MetaFooter meta={turn.meta} />}
          </div>
        ))}
      </div>
      <div className="flex gap-2 border-t p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about the material…"
          className="flex-1 rounded-lg border px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          onClick={send}
          disabled={streaming}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}

function MetaFooter({ meta }: { meta: ChatMeta }) {
  return (
    <div className="mt-1 space-y-1 text-left">
      {meta.off_syllabus && (
        <span className="inline-block rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
          off-syllabus → redirected
        </span>
      )}
      {meta.citations.map((c: Citation, i) => (
        <div key={i} className="text-xs text-gray-500">
          <span className="font-medium text-indigo-600">
            [{c.source}
            {c.page ? ` p.${c.page}` : ""}]
          </span>{" "}
          “{c.quote}…”
        </div>
      ))}
      <div className="text-[11px] text-gray-400">
        {meta.grounded ? "✓ grounded" : "⚠ ungrounded"} · model {meta.model}
        {meta.ttft_ms != null && ` · TTFT ${Math.round(meta.ttft_ms)}ms`}
        {meta.cached_input_tokens + meta.uncached_input_tokens > 0 &&
          ` · cache ${Math.round(
            (100 * meta.cached_input_tokens) /
              (meta.cached_input_tokens + meta.uncached_input_tokens)
          )}%`}
      </div>
    </div>
  );
}
