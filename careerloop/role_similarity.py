"""
Phase E — Embedding-based role relevance filter.

Uses sentence-transformers (all-MiniLM-L6-v2) for cosine similarity.
Falls back to token overlap if sentence-transformers not installed.
"""

import logging
import re
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

THRESHOLD = 0.40  # below this → irrelevant
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall(text.lower()))


def _token_overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


class RoleSimilarityFilter:
    """
    Filter jobs whose title/role has insufficient similarity to the target role.
    Uses sentence-transformers when available, token overlap as fallback.
    """

    def __init__(self, threshold: float = THRESHOLD):
        self.threshold = threshold
        self._model = None
        self._use_embeddings = None

    def _get_model(self):
        if self._use_embeddings is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._use_embeddings = True
                logger.info("[RoleSimilarity] Using sentence-transformers")
            except ImportError:
                self._use_embeddings = False
                logger.info("[RoleSimilarity] sentence-transformers not installed, using token overlap")
        return self._model

    def similarity(self, text_a: str, text_b: str) -> float:
        model = self._get_model()
        if model and self._use_embeddings:
            try:
                import numpy as np
                vecs = model.encode([text_a, text_b], normalize_embeddings=True)
                return float(np.dot(vecs[0], vecs[1]))
            except Exception as e:
                logger.debug(f"[RoleSimilarity] embedding failed: {e}")
        return _token_overlap(text_a, text_b)

    def is_relevant(self, job: dict, target_role: str, target_functions: list = None) -> bool:
        title = job.get("title", "")
        if not title:
            return False

        # Check against target role
        if self.similarity(title, target_role) >= self.threshold:
            return True

        # Check against any target function
        if target_functions:
            for fn in target_functions:
                if self.similarity(title, fn) >= self.threshold:
                    return True

        return False

    def filter_jobs(
        self,
        jobs: list[dict],
        target_role: str,
        target_functions: list = None,
        rejected_roles: list = None,
    ) -> tuple[list[dict], int]:
        """
        Returns (relevant_jobs, rejected_count).
        rejected_roles checked first (hard reject by string match).
        """
        rejected_terms = {r.lower() for r in (rejected_roles or [])}
        kept = []
        rejected = 0

        for job in jobs:
            title = job.get("title", "").lower()

            # Hard reject by profile rejected_roles
            if any(r in title for r in rejected_terms):
                rejected += 1
                continue

            if self.is_relevant(job, target_role, target_functions):
                kept.append(job)
            else:
                rejected += 1

        return kept, rejected
