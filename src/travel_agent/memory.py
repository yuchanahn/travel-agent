"""Local, scoped memory retrieval over immutable conversation/tool events."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                user_id TEXT NOT NULL, session_id TEXT NOT NULL, event_id TEXT NOT NULL,
                timestamp TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (user_id, session_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS indexes (
                user_id TEXT NOT NULL, session_id TEXT NOT NULL,
                snapshot TEXT NOT NULL, config TEXT NOT NULL,
                PRIMARY KEY (user_id, session_id)
            );
            CREATE TABLE IF NOT EXISTS chunks (
                user_id TEXT NOT NULL, session_id TEXT NOT NULL, chunk_id TEXT NOT NULL,
                payload TEXT NOT NULL, vector BLOB NOT NULL, dimensions INTEGER NOT NULL,
                PRIMARY KEY (user_id, session_id, chunk_id)
            );
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def add(self, user: str, session: str, events: list[dict]) -> int:
        if not user.strip() or not session.strip():
            raise ValueError("user and session must be non-empty")
        inserted = 0
        with self.db:
            for event in events:
                required = ("event_id", "turn_id", "timestamp", "role", "content")
                if any(not isinstance(event.get(key), str) or not event[key].strip() for key in required):
                    raise ValueError(f"Each event requires non-empty strings: {required}")
                if event["role"] not in {"user", "assistant", "tool"}:
                    raise ValueError("Only user/assistant/tool events can be imported")
                timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    raise ValueError("Event timestamps must contain a timezone")
                utc = timestamp.astimezone(timezone.utc).isoformat()
                payload = canonical(event)  # Preserve original content and metadata, including timezone.
                previous = self.db.execute(
                    "SELECT payload FROM events WHERE user_id=? AND session_id=? AND event_id=?",
                    (user, session, event["event_id"]),
                ).fetchone()
                if previous:
                    if previous[0] != payload:
                        raise ValueError("Existing event is immutable; append a new event for a correction")
                    continue
                self.db.execute("INSERT INTO events VALUES (?,?,?,?,?)", (user, session, event["event_id"], utc, payload))
                inserted += 1
        return inserted

    def events(self, user: str, session: str) -> list[dict]:
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT payload FROM events WHERE user_id=? AND session_id=? ORDER BY timestamp,event_id",
            (user, session),
        )]

    def save_index(self, user, session, snapshot, config, chunks, vectors):
        with self.db:
            if digest(self.events(user, session)) != snapshot:
                raise ValueError("History changed during indexing; rebuild the index")
            self.db.execute("DELETE FROM chunks WHERE user_id=? AND session_id=?", (user, session))
            for chunk, vector in zip(chunks, vectors, strict=True):
                self.db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?)", (
                    user, session, chunk["chunk_id"], canonical(chunk), vector.astype("<f4").tobytes(), len(vector),
                ))
            self.db.execute("INSERT OR REPLACE INTO indexes VALUES (?,?,?,?)", (user, session, snapshot, canonical(config)))

    def read_index(self, user, session):
        import numpy as np

        metadata = self.db.execute("SELECT snapshot,config FROM indexes WHERE user_id=? AND session_id=?", (user, session)).fetchone()
        if not metadata:
            raise ValueError("No index for this user/session. Run memory index first.")
        if digest(self.events(user, session)) != metadata[0]:
            raise ValueError("History changed; run memory index again before searching.")
        rows = self.db.execute("SELECT payload,vector,dimensions FROM chunks WHERE user_id=? AND session_id=? ORDER BY chunk_id", (user, session)).fetchall()
        if not rows:
            raise ValueError("The memory index is empty")
        chunks = [json.loads(row[0]) for row in rows]
        vectors = np.stack([np.frombuffer(row[1], dtype="<f4", count=row[2]) for row in rows])
        return json.loads(metadata[1]), chunks, vectors


class Encoder:
    def __init__(self, revision: str | None = None):
        import os
        import torch
        from huggingface_hub import model_info
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(int(os.environ.get("MEMORY_CPU_THREADS", "4")))
        self.name = "intfloat/multilingual-e5-small"
        self.revision = revision or model_info(self.name).sha
        self.model = SentenceTransformer(self.name, revision=self.revision, device="cpu", trust_remote_code=False)
        self.model.max_seq_length = 512
        self.tokenizer = self.model.tokenizer

    def encode(self, texts, *, query=False):
        prefix = "query: " if query else "passage: "
        return self.model.encode([prefix + text for text in texts], normalize_embeddings=True, batch_size=8, show_progress_bar=False)


@lru_cache(maxsize=2)
def get_encoder(revision=None):
    return Encoder(revision)


def make_chunks(events: list[dict], tokenizer, size=240, overlap=32):
    """Group adjacent events by turn; retain exact text and offsets for long turns."""
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("Invalid chunk size/overlap")
    groups: list[list[dict]] = []
    for event in events:
        if not groups or groups[-1][-1]["turn_id"] != event["turn_id"]:
            groups.append([])
        groups[-1].append(event)
    chunks = []
    for group in groups:
        text = "\n".join(
            f"[{event['event_id']} | {event['timestamp']} | {event['role']}"
            f" | source={event.get('source_url', 'conversation')}]\n{event['content']}"
            for event in group
        )
        offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
        for start in range(0, len(offsets), size - overlap):
            end = min(start + size, len(offsets))
            left, right = offsets[start][0], offsets[end - 1][1]
            part = text[left:right]
            if len(tokenizer.encode("passage: " + part)) > 512:
                raise ValueError("Chunk exceeds embedding model context; reduce chunk size")
            chunks.append({
                "chunk_id": "m-" + digest([group, left, right])[:20],
                "turn_id": group[0]["turn_id"], "text": part,
                "timestamp": group[-1]["timestamp"], "start_char": left, "end_char": right,
                "events": [{key: event.get(key) for key in ("event_id", "timestamp", "role", "source_url")} for event in group],
            })
            if end == len(offsets):
                break
    return chunks


def build_index(store: MemoryStore, user: str, session: str):
    from importlib.metadata import version

    events = store.events(user, session)
    if not events:
        raise ValueError("No events in this user/session")
    encoder = get_encoder()
    chunks = make_chunks(events, encoder.tokenizer)
    vectors = encoder.encode([chunk["text"] for chunk in chunks])
    config = {
        "schema_version": 1, "chunker": "adjacent-turn-token-windows-v1", "chunk_size": 240, "overlap": 32,
        "embedding_model": encoder.name, "revision": encoder.revision, "normalized": True,
        "device": "cpu", "query_prefix": "query: ", "passage_prefix": "passage: ",
        "packages": {name: version(name) for name in ("sentence-transformers", "rank-bm25", "kiwipiepy", "numpy")},
    }
    store.save_index(user, session, digest(events), config, chunks, vectors)
    return {"events": len(events), "chunks": len(chunks), "config": config}


def rrf(rankings: list[list[int]], k=60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, 1):
            scores[index] = scores.get(index, 0.0) + 1 / (k + rank)
    return scores


def build_bm25_index(store: MemoryStore, user: str, session: str):
    """Index exact event windows without an embedding model or downloads."""
    import numpy as np
    events = store.events(user, session)
    chunks = []
    for event in events:
        text = event['content']
        for left in range(0, len(text), 260):
            right = min(len(text), left + 300)
            chunks.append({
                'chunk_id': 'm-' + digest([event, left, right])[:20],
                'turn_id': event['turn_id'], 'timestamp': event['timestamp'],
                'start_char': left, 'end_char': right,
                'text': f"[{event['role']} | {event['timestamp']}]\n" + text[left:right],
                'events': [{key: event.get(key) for key in ('event_id','timestamp','role','source_url')}],
            })
            if right == len(text):
                break
    config = {'schema_version': 1, 'lexical_only': True, 'tokenizer': 'ko-bigram-v1',
              'chunker': 'event-char-windows-v1', 'chunk_size_chars': 300, 'overlap_chars': 40}
    # Zero-dimensional rows explicitly represent the absence of embeddings.
    store.save_index(user, session, digest(events), config, chunks, np.empty((len(chunks), 0), dtype=np.float32))
    return {'events': len(events), 'chunks': len(chunks), 'config': config}


def search(store: MemoryStore, user: str, session: str, query: str, *, mode="hybrid", top_k=5, candidates=20, rerank=False):
    import numpy as np
    from rank_bm25 import BM25Okapi

    if not query.strip() or not 1 <= top_k <= 20 or not 1 <= candidates <= 100:
        raise ValueError("Provide a non-empty query; top_k 1..20 and candidates 1..100")
    if mode not in {"bm25", "dense", "hybrid"}:
        raise ValueError("Unknown retrieval mode")
    config, chunks, vectors = store.read_index(user, session)
    if config.get('lexical_only'):
        if mode != 'bm25' or rerank:
            raise ValueError('This lexical-only index supports bm25 without reranking; build a full index for dense/hybrid')
        from .lexical import tokens
    else:
        from kiwipiepy import Kiwi
        kiwi = Kiwi(num_workers=1)
        def tokens(text):
            punctuation = {"SF", "SP", "SS", "SSO", "SSC", "SE", "SO", "SW"}
            return [token.form.lower() for token in kiwi.tokenize(text) if not token.tag.startswith(("J", "E")) and token.tag not in punctuation]
    lexical = np.zeros(len(chunks))
    sparse_rank = []
    if mode != "dense":
        query_tokens = tokens(query)
        corpus = [tokens(chunk["text"]) for chunk in chunks]
        if not any(corpus):
            raise ValueError("No searchable lexical tokens")
        lexical = BM25Okapi(corpus).get_scores(query_tokens)
        # rank_bm25 scores are not probabilities; don't interpret <=0 as irrelevance.
        matched = [i for i, terms in enumerate(corpus) if set(query_tokens).intersection(terms)]
        sparse_rank = sorted(matched, key=lambda i: (-float(lexical[i]), chunks[i]["chunk_id"]))[:candidates]
    dense = np.zeros(len(chunks))
    dense_rank = []
    if mode != "bm25":
        encoder = get_encoder(config["revision"])
        if len(encoder.tokenizer.encode("query: " + query)) > 512:
            raise ValueError("Query exceeds embedding context; supply a focused search query")
        dense = vectors @ encoder.encode([query], query=True)[0]
        dense_rank = sorted(range(len(chunks)), key=lambda i: (-float(dense[i]), chunks[i]["chunk_id"]))[:candidates]
    rankings = [sparse_rank] if mode == "bm25" else [dense_rank] if mode == "dense" else [sparse_rank, dense_rank]
    fused = rrf(rankings)
    order = sorted(fused, key=lambda i: (-fused[i], chunks[i]["chunk_id"]))[:candidates]
    rerank_scores = {}
    reranker_revision = None
    if rerank and order:
        from huggingface_hub import model_info
        from sentence_transformers import CrossEncoder
        reranker_revision = model_info("BAAI/bge-reranker-v2-m3").sha
        reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", revision=reranker_revision, device="cpu", max_length=512, trust_remote_code=False)
        values = reranker.predict([(query, chunks[i]["text"]) for i in order], batch_size=2, show_progress_bar=False)
        rerank_scores = {i: float(score) for i, score in zip(order, values, strict=True)}
        order.sort(key=lambda i: (-rerank_scores[i], chunks[i]["chunk_id"]))
    hits = []
    for i in order[:top_k]:
        hit = dict(chunks[i])
        hit["scores"] = {"bm25": float(lexical[i]) if mode != "dense" else None, "dense": float(dense[i]) if dense_rank else None, "rrf": fused[i], "reranker": rerank_scores.get(i)}
        hits.append(hit)
    return {"mode": mode, "reranked": rerank, "reranker_revision": reranker_revision,
            "historical_only": True, "web_search_performed": False, "hits": hits}
