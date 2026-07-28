"""Retrieval pipeline: parse -> chunk -> embed -> store -> retrieve.

Design goal: run everywhere. Embeddings prefer `sentence-transformers`
(all-MiniLM-L6-v2) but fall back to a deterministic hashing vectorizer if the
model isn't installed. The vector store prefers persistent ChromaDB but falls
back to an in-process NumPy store. Either way the public API is identical, so
the rest of the app never has to care which backend is live.
"""
from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .config import get_settings
from .models import Chunk

# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
_st_model = None
_st_tried = False


def _get_st_model():
    global _st_model, _st_tried
    if _st_tried:
        return _st_model
    _st_tried = True
    try:  # pragma: no cover - depends on optional heavy dependency
        from sentence_transformers import SentenceTransformer

        _st_model = SentenceTransformer(get_settings().embedding_model)
    except Exception:
        _st_model = None
    return _st_model


_HASH_DIM = 384  # matches all-MiniLM-L6-v2 so both backends are interchangeable


def _hash_embed(text: str) -> list[float]:
    """Deterministic bag-of-words hashing embedding. Not as good as a real
    model, but keeps retrieval meaningful with zero downloads."""
    vec = [0.0] * _HASH_DIM
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % _HASH_DIM] += 1.0
        # a second hashed dimension reduces collisions
        vec[(h // _HASH_DIM) % _HASH_DIM] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(texts: list[str]) -> list[list[float]]:
    model = _get_st_model()
    if model is not None:  # pragma: no cover
        return [v.tolist() for v in model.encode(texts, normalize_embeddings=True)]
    return [_hash_embed(t) for t in texts]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # inputs are unit-normalised


# --------------------------------------------------------------------------- #
# PDF / markdown parsing
# --------------------------------------------------------------------------- #
def parse_document(filename: str, data: bytes) -> list[tuple[str, Optional[int]]]:
    """Return a list of (text, page_number). page is None for markdown/text."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _parse_pdf(data)
    text = data.decode("utf-8", errors="replace")
    return [(text, None)]


def _parse_pdf(data: bytes) -> list[tuple[str, Optional[int]]]:
    try:  # pragma: no cover - optional dependency
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        return [(page.get_text(), i + 1) for i, page in enumerate(doc)]
    except Exception:
        # Last-ditch: treat the bytes as text so upload still succeeds.
        return [(data.decode("utf-8", errors="replace"), None)]


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def _word_chunks(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    step = max(size - overlap, 1)
    while start < len(words):
        chunk = " ".join(words[start : start + size]).strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def chunk_document(pages: list[tuple[str, Optional[int]]]) -> list[tuple[str, Optional[int]]]:
    settings = get_settings()
    # ~1.3 words/token is a decent heuristic for English prose.
    size = int(settings.chunk_tokens * 1.3)
    overlap = int(settings.chunk_overlap * 1.3)
    out: list[tuple[str, Optional[int]]] = []
    for text, page in pages:
        for chunk in _word_chunks(text, size, overlap):
            out.append((chunk, page))
    return out


# --------------------------------------------------------------------------- #
# Vector store
# --------------------------------------------------------------------------- #
@dataclass
class _MemStore:
    """In-process fallback store, one collection per session id."""
    collections: dict[str, list[Chunk]] = field(default_factory=dict)
    vectors: dict[str, list[list[float]]] = field(default_factory=dict)

    def add(self, session_id: str, chunks: list[Chunk], vecs: list[list[float]]) -> None:
        self.collections.setdefault(session_id, [])
        self.vectors.setdefault(session_id, [])
        self.collections[session_id].extend(chunks)
        self.vectors[session_id].extend(vecs)

    def query(self, session_id: str, qvec: list[float], k: int) -> list[Chunk]:
        chunks = self.collections.get(session_id, [])
        vecs = self.vectors.get(session_id, [])
        scored = sorted(
            (
                (_cosine(qvec, v), c.model_copy(update={"score": _cosine(qvec, v)}))
                for c, v in zip(chunks, vecs)
            ),
            key=lambda t: t[0],
            reverse=True,
        )
        return [c for _, c in scored[:k]]

    def count(self, session_id: str) -> int:
        return len(self.collections.get(session_id, []))


_mem = _MemStore()
_chroma_client = None
_chroma_tried = False


def _get_chroma():
    global _chroma_client, _chroma_tried
    if _chroma_tried:
        return _chroma_client
    _chroma_tried = True
    try:  # pragma: no cover - optional dependency
        import chromadb

        _chroma_client = chromadb.PersistentClient(path=get_settings().chroma_dir)
    except Exception:
        _chroma_client = None
    return _chroma_client


def _collection_name(session_id: str) -> str:
    return "s_" + re.sub(r"[^a-zA-Z0-9]", "", session_id)[:60]


def index_document(session_id: str, filename: str, data: bytes) -> int:
    """Parse, chunk, embed and store a document. Returns the chunk count."""
    pages = parse_document(filename, data)
    pieces = chunk_document(pages)
    if not pieces:
        return 0

    chunks: list[Chunk] = []
    texts: list[str] = []
    for text, page in pieces:
        chunks.append(
            Chunk(id=str(uuid.uuid4()), text=text, source=filename, page=page)
        )
        texts.append(text)
    vecs = embed(texts)

    client = _get_chroma()
    if client is not None:  # pragma: no cover
        coll = client.get_or_create_collection(_collection_name(session_id))
        coll.add(
            ids=[c.id for c in chunks],
            embeddings=vecs,
            documents=texts,
            metadatas=[{"source": c.source, "page": c.page or -1} for c in chunks],
        )
    else:
        _mem.add(session_id, chunks, vecs)
    return len(chunks)


def retrieve(session_id: str, query: str, k: Optional[int] = None) -> list[Chunk]:
    settings = get_settings()
    k = k or settings.retrieve_k
    qvec = embed([query])[0]

    client = _get_chroma()
    if client is not None:  # pragma: no cover
        try:
            coll = client.get_collection(_collection_name(session_id))
        except Exception:
            return []
        res = coll.query(query_embeddings=[qvec], n_results=k)
        out: list[Chunk] = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[None] * len(ids)])[0]
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            score = 1.0 - dist if dist is not None else 0.0
            page = meta.get("page", -1)
            out.append(
                Chunk(
                    id=cid,
                    text=doc,
                    source=meta.get("source", "unknown"),
                    page=None if page == -1 else page,
                    score=score,
                )
            )
        return out

    return _mem.query(session_id, qvec, k)


def has_corpus(session_id: str) -> bool:
    client = _get_chroma()
    if client is not None:  # pragma: no cover
        try:
            return client.get_collection(_collection_name(session_id)).count() > 0
        except Exception:
            return False
    return _mem.count(session_id) > 0


def course_digest(session_id: str, max_chars: int = 12000) -> str:
    """A STABLE snapshot of the course text for this session, in a fixed order.

    This is what goes in the cached prompt prefix: because it does not change
    from turn to turn, Anthropic prompt caching can reuse it. Per-turn retrieved
    chunks go in the (uncached) message instead. Capped so a large upload
    doesn't blow up the prompt.
    """
    client = _get_chroma()
    texts: list[str] = []
    if client is not None:  # pragma: no cover
        try:
            got = client.get_collection(_collection_name(session_id)).get()
            texts = got.get("documents", []) or []
        except Exception:
            texts = []
    else:
        texts = [c.text for c in _mem.collections.get(session_id, [])]

    out, total = [], 0
    for t in texts:
        if total + len(t) > max_chars:
            break
        out.append(t)
        total += len(t)
    return "\n\n".join(out)
