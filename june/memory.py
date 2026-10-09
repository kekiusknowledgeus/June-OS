"""Replaceable local latent semantic retrieval; no network or model downloads."""
from typing import Protocol
import re
import math
import time
import numpy as np


class EmbeddingProvider(Protocol):
    def rank(self, query: str, documents: list[str]) -> list[float]: ...


class LocalSemanticIndex:
    # Concept expansion supplements corpus-trained latent semantic analysis on tiny corpora.
    concepts = ["wireless cordless inductive induction power charging electricity", "robot robotics humanoid android", "flight flying fly aerial airborne", "bug error failure broken debug fix", "decision decided choice chose", "task work unfinished todo pending", "yesterday past previous earlier history", "meeting appointment calendar schedule"]

    def __init__(self):
        self.cache = {}

    def tokens(self, text):
        tokens = re.findall(r"\w+", text.lower())
        for i, group in enumerate(self.concepts):
            if set(tokens) & set(group.split()):
                tokens += [f"concept{i}"] * 3
        return tokens

    def rank(self, query, documents):
        key = (query, tuple(documents))
        if key not in self.cache:
            if len(self.cache) >= 16:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = self._rank(query, documents)
        return list(self.cache[key])

    def _rank(self, query, documents):
        if not documents:
            return []
        rows = [self.tokens(d) for d in documents] + [self.tokens(query)]
        vocab = sorted(set(t for row in rows for t in row))[:20000]
        idx = {t: i for i, t in enumerate(vocab)}
        matrix = np.zeros((len(rows), len(vocab)))
        for i, row in enumerate(rows):
            for t in row:
                if t in idx:
                    matrix[i, idx[t]] += 1
        matrix *= np.log((len(rows) + 1) / (1 + (matrix > 0).sum(axis=0))) + 1
        matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-8)
        lexical = matrix[:-1] @ matrix[-1]
        if len(documents) > 4 and matrix.shape[1] > 4:
            u, s, _ = np.linalg.svd(matrix, full_matrices=False)
            latent = u[:, :min(32, len(documents) - 1)] * s[:min(32, len(documents) - 1)]
            latent /= np.maximum(np.linalg.norm(latent, axis=1, keepdims=True), 1e-8)
            lexical = .65 * lexical + .35 * (latent[:-1] @ latent[-1])
        return lexical.tolist()


class Memory:
    def __init__(self, store, embeddings=None):
        self.store = store
        self.embeddings = embeddings or LocalSemanticIndex()

    def remember(self, text, category="knowledge", explicit=False, source="user", confidence=.7, importance=.5, project=None, tags=None, people=None, subject=None, pinned=False):
        if not text.strip() or len(text) > 12000:
            raise ValueError("Memory must contain 1–12000 characters")
        norm = " ".join(text.lower().split())
        for row in self.store.list("memory", 10000):
            if row["normalized"] == norm:
                sources = list(dict.fromkeys(row.get("sources", [row["source"]]) + [source]))
                return self.store.put("memory", {"last_seen": time.time(), "explicit": row["explicit"] or explicit, "confidence": max(confidence, row["confidence"]), "sources": sources, "pinned": row.get("pinned", False) or pinned}, row["id"])
        conflicts = [row["id"] for row in self.store.list("memory") if subject and row.get("subject") == subject and row.get("status", "active") == "active"]
        item = self.store.put("memory", {"text": text, "normalized": norm, "category": category, "explicit": explicit, "source": source, "sources": [source], "confidence": confidence, "importance": importance, "project": project, "last_seen": time.time(), "last_accessed": None, "tags": tags or [], "people": people or [], "subject": subject, "pinned": pinned, "status": "active", "conflicts": conflicts})
        for id in conflicts:
            row = self.store.get("memory", id)
            self.store.put("memory", {"conflicts": list(dict.fromkeys(row.get("conflicts", []) + [item["id"]]))}, id)
        return item

    def search(self, query, limit=8):
        rows = [r for r in self.store.list("memory", 2000) if r.get("status", "active") == "active"]
        scores = self.embeddings.rank(query, [x["text"] for x in rows])
        ranked = []
        for row, similarity in zip(rows, scores):
            if similarity <= .025:
                continue
            age_days = (time.time() - row["last_seen"]) / 86400
            persistence = 1 if row["explicit"] or row.get("pinned") else math.exp(-age_days / 180)
            score = similarity * (.7 + .3 * row["importance"]) * persistence
            ranked.append({**row, "score": round(score, 4)})
        chosen = sorted(ranked, key=lambda x: x["score"], reverse=True)[:limit]
        for row in chosen:
            self.store.put("memory", {"last_accessed": time.time()}, row["id"])
        return chosen

    def manage(self, id, action, text=None, other_id=None):
        row = self.store.get("memory", id)
        if not row:
            raise ValueError("Memory unavailable")
        if action == "forget":
            self.store.delete("memory", id)
            return {"status": "forgotten", "id": id}
        if action in {"pin", "unpin"}:
            return self.store.put("memory", {"pinned": action == "pin"}, id)
        if action == "update":
            if not text or len(text) > 12000:
                raise ValueError("Updated memory content is required")
            self.store.put("memory_revision", {"memory": id, "previous": row, "reason": "explicit update"})
            return self.store.put("memory", {"text": text, "normalized": " ".join(text.lower().split()), "conflicts": [], "source": "user-approved update"}, id)
        if action in {"merge", "resolve"}:
            other = self.store.get("memory", other_id)
            if not other or other_id == id:
                raise ValueError("Select a different existing memory")
            merged = self.manage(id, "update", text or row["text"])
            self.store.put("memory", {"status": "superseded", "superseded_by": id}, other_id)
            return self.store.put("memory", {"sources": list(dict.fromkeys(row.get("sources", [row["source"]]) + other.get("sources", [other["source"]]))), "explicit": row["explicit"] or other["explicit"]}, merged["id"])
        raise ValueError("Unknown memory management action")

    def candidates(self, text, source):
        if re.match(r"(?i)^(remember|remember that|remember this)\b", text):
            return [self.remember(re.sub(r"(?i)^remember(?: that| this)?\s*", "", text), explicit=True, confidence=1, importance=.9, source=source)]
        return []
