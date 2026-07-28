import { useRef, useState } from "react";
import { uploadDocument } from "../api";

interface Props {
  sessionId: string;
  onUploaded: (sessionId: string, filename: string, chunks: number) => void;
}

export default function UploadZone({ sessionId, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function handleFile(file: File) {
    setBusy(true);
    setStatus(`Indexing ${file.name}…`);
    try {
      const res = await uploadDocument(file, sessionId);
      setStatus(`Indexed ${res.chunks_indexed} chunks from ${res.filename}`);
      onUploaded(res.session_id, res.filename, res.chunks_indexed);
    } catch {
      setStatus("Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border-2 border-dashed border-indigo-200 bg-white p-4">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.md,.txt,.markdown"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium">Upload course material</p>
          <p className="text-xs text-gray-500">PDF or Markdown</p>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Working…" : "Choose file"}
        </button>
      </div>
      {status && <p className="mt-2 text-xs text-gray-600">{status}</p>}
    </div>
  );
}
