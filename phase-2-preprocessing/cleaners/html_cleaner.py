import re
from bs4 import BeautifulSoup

_BLOCK_TAGS = frozenset({"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td"})
_HTML_PATTERN = re.compile(r"<[a-zA-Z/][^>]*>|&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;")


class HTMLCleaner:
    """Strip HTML tags and decode entities using BeautifulSoup.

    Block-level elements are replaced with newlines to preserve paragraph breaks.
    """

    def clean(self, text: str) -> tuple[str, bool]:
        """Return (cleaned_text, was_modified)."""
        if not _HTML_PATTERN.search(text):
            return text, False

        soup = BeautifulSoup(text, "html.parser")

        for tag in soup.find_all(_BLOCK_TAGS):
            tag.insert_before("\n")

        cleaned = soup.get_text(separator="")
        return cleaned, True
