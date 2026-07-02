import unicodedata


class SpecialCharFilter:
    """Remove non-printable and Unicode control characters.

    Preserves newlines and tabs — they carry structural meaning in review text.
    """

    def clean(self, text: str) -> str:
        return "".join(
            ch for ch in text
            if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\t")
        )
