import re


class WhitespaceCleaner:
    """Collapse excess whitespace and normalize line endings."""

    def clean(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()
