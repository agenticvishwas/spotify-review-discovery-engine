import emoji as emoji_lib


class EmojiHandler:
    """Remove or replace emoji characters.

    mode='remove' (default): strip emoji entirely.
    mode='replace': substitute with text descriptions via the emoji library.
    """

    def __init__(self, mode: str = "remove"):
        if mode not in ("remove", "replace"):
            raise ValueError(f"mode must be 'remove' or 'replace', got '{mode}'")
        self._mode = mode

    def handle(self, text: str) -> tuple[str, bool]:
        """Return (processed_text, was_modified)."""
        if not emoji_lib.emoji_list(text):
            return text, False

        if self._mode == "replace":
            result = emoji_lib.demojize(text, delimiters=(" :", ": "))
        else:
            result = emoji_lib.replace_emoji(text, replace="")

        return result, result != text
