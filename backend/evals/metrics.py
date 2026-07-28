"""Metric computation for the eval harness."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunMetrics:
    label: str
    groundedness: float = 0.0        # % answerable answers supported by a chunk
    off_syllabus_handling: float = 0.0  # % of off/adversarial correctly refused
    quiz_validity: float = 0.0       # % generated quizzes passing schema + answerability
    unsupported_rate: float = 0.0    # % answerable answers NOT supported (the headline number)
    ttft_p50_ms: float = 0.0
    ttft_p95_ms: float = 0.0
    cached_tokens: int = 0
    uncached_tokens: int = 0
    n_answerable: int = 0
    n_refusal_targets: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def cache_reduction_pct(self) -> float:
        total = self.cached_tokens + self.uncached_tokens
        return 100.0 * self.cached_tokens / total if total else 0.0

    def to_row(self) -> dict:
        return {
            "label": self.label,
            "groundedness_%": round(self.groundedness, 1),
            "unsupported_%": round(self.unsupported_rate, 1),
            "off_syllabus_handling_%": round(self.off_syllabus_handling, 1),
            "quiz_validity_%": round(self.quiz_validity, 1),
            "ttft_p50_ms": round(self.ttft_p50_ms, 1),
            "ttft_p95_ms": round(self.ttft_p95_ms, 1),
            "cache_reduction_%": round(self.cache_reduction_pct, 1),
        }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)
