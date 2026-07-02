import re

_SENTENCE_SPLIT = re.compile(r"[.!?]+")

_GENERIC_TEMPLATES = frozenset({
    "great app", "love this app", "best app ever", "best app",
    "terrible app", "worst app ever", "worst app",
    "good app", "bad app", "okay app", "ok app", "nice app",
    "love it", "hate it", "awesome", "awful",
    "5 stars", "1 star", "perfect", "garbage",
})

_SPECIFIC_PATTERNS = [
    re.compile(r"\b(feature|bug|crash|update|version|broke?|fixed?|slow|fast|issue)\b", re.I),
    re.compile(r"\b(playlist|shuffle|podcast|offline|download|stream|discover|recommend)\b", re.I),
    re.compile(r"\b(because|but|however|although|since|when|after|before|while|although)\b", re.I),
    re.compile(r"\b(used to|used to be|before the|after the|since the)\b", re.I),
]


class QualityScorer:
    """Score review quality 0.0–1.0 based on substantiveness.

    Scoring function (deterministic, per architecture spec):
        word_count >= 10  → +0.3
        word_count >= 30  → +0.2
        sentence_count >= 2  → +0.2
        contains_specific_content  → +0.2
        not_generic_template  → +0.1
    """

    def score(self, text: str) -> float:
        wc = self.word_count(text)
        sc = self.sentence_count(text)

        result = 0.0
        if wc >= 10:
            result += 0.3
        if wc >= 30:
            result += 0.2
        if sc >= 2:
            result += 0.2
        if self._has_specific_content(text):
            result += 0.2
        if wc >= 3 and not self._is_generic_template(text):
            result += 0.1

        return round(min(result, 1.0), 4)

    def word_count(self, text: str) -> int:
        return len(text.split())

    def sentence_count(self, text: str) -> int:
        parts = _SENTENCE_SPLIT.split(text)
        return sum(1 for p in parts if p.strip())

    def _has_specific_content(self, text: str) -> bool:
        return any(p.search(text) for p in _SPECIFIC_PATTERNS)

    def _is_generic_template(self, text: str) -> bool:
        return text.strip().lower() in _GENERIC_TEMPLATES
