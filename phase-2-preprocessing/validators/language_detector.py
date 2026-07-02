import logging

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 20
CONFIDENCE_THRESHOLD = 0.90

try:
    from langdetect import detect_langs, LangDetectException
    from langdetect import DetectorFactory
    DetectorFactory.seed = 42  # deterministic output
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.warning("langdetect not installed — language detection will assume English")


class LanguageDetector:
    """Detect the language of review text using langdetect.

    Returns ISO 639-1 codes. Reviews below the confidence threshold or shorter
    than MIN_TEXT_LENGTH are tagged 'unknown' and excluded from AI analysis.
    """

    def detect(self, text: str) -> tuple[str, float]:
        """Return (language_code, confidence). Returns ('unknown', 0.0) on failure."""
        if len(text.strip()) < MIN_TEXT_LENGTH:
            return "unknown", 0.0

        if not _AVAILABLE:
            return "en", 1.0

        try:
            langs = detect_langs(text)
            if not langs:
                return "unknown", 0.0
            best = langs[0]
            if best.prob < CONFIDENCE_THRESHOLD:
                return "unknown", round(best.prob, 4)
            return best.lang, round(best.prob, 4)
        except LangDetectException as exc:
            logger.debug("Language detection failed: %s", exc)
            return "unknown", 0.0

    def is_english(self, text: str) -> bool:
        lang, confidence = self.detect(text)
        return lang == "en" and confidence >= CONFIDENCE_THRESHOLD
