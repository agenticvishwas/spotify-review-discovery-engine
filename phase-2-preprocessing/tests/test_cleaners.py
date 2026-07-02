import pytest
from cleaners.html_cleaner import HTMLCleaner
from cleaners.emoji_handler import EmojiHandler
from cleaners.whitespace_cleaner import WhitespaceCleaner
from cleaners.special_char_filter import SpecialCharFilter


class TestHTMLCleaner:
    def setup_method(self):
        self.cleaner = HTMLCleaner()

    def test_plain_text_unchanged(self):
        text = "This is a plain review with no HTML."
        result, modified = self.cleaner.clean(text)
        assert result == text
        assert modified is False

    def test_strips_basic_tags(self):
        text = "<p>Great app</p>"
        result, modified = self.cleaner.clean(text)
        assert "<p>" not in result
        assert "Great app" in result
        assert modified is True

    def test_decodes_html_entities(self):
        text = "Spotify &amp; podcasts are great. &lt;3"
        result, modified = self.cleaner.clean(text)
        assert "&amp;" not in result
        assert "Spotify" in result
        assert modified is True

    def test_block_tags_add_newline(self):
        text = "<p>First paragraph.</p><p>Second paragraph.</p>"
        result, _ = self.cleaner.clean(text)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_script_tags_stripped(self):
        text = "Review text <script>alert('xss')</script> more text"
        result, modified = self.cleaner.clean(text)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Review text" in result
        assert modified is True

    def test_numeric_html_entity(self):
        text = "Love Spotify&#33;"
        result, modified = self.cleaner.clean(text)
        assert "&#33;" not in result
        assert modified is True

    def test_empty_string(self):
        result, modified = self.cleaner.clean("")
        assert result == ""
        assert modified is False


class TestEmojiHandler:
    def setup_method(self):
        self.handler = EmojiHandler(mode="remove")

    def test_no_emoji_unchanged(self):
        text = "Great app, works well."
        result, modified = self.handler.handle(text)
        assert result == text
        assert modified is False

    def test_removes_emoji(self):
        text = "Best app ever 😍🎵"
        result, modified = self.handler.handle(text)
        assert "😍" not in result
        assert "🎵" not in result
        assert modified is True

    def test_replace_mode(self):
        handler = EmojiHandler(mode="replace")
        text = "Love it 😍"
        result, modified = handler.handle(text)
        assert "😍" not in result
        assert modified is True

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            EmojiHandler(mode="invalid")

    def test_mixed_emoji_and_text(self):
        text = "bestt😭🫶🏻"
        result, modified = self.handler.handle(text)
        assert "😭" not in result
        assert "bestt" in result
        assert modified is True


class TestWhitespaceCleaner:
    def setup_method(self):
        self.cleaner = WhitespaceCleaner()

    def test_collapses_multiple_spaces(self):
        text = "This  has   multiple    spaces."
        result = self.cleaner.clean(text)
        assert "  " not in result
        assert "This has multiple spaces." == result

    def test_normalizes_crlf(self):
        text = "Line one\r\nLine two\r\nLine three"
        result = self.cleaner.clean(text)
        assert "\r" not in result
        assert "Line one" in result
        assert "Line two" in result

    def test_collapses_multiple_newlines(self):
        text = "Paragraph one.\n\n\n\n\nParagraph two."
        result = self.cleaner.clean(text)
        assert "\n\n\n" not in result

    def test_strips_leading_trailing_whitespace(self):
        text = "   Hello world.   "
        result = self.cleaner.clean(text)
        assert result == "Hello world."

    def test_preserves_single_newlines(self):
        text = "First line.\nSecond line."
        result = self.cleaner.clean(text)
        assert "First line." in result
        assert "Second line." in result


class TestSpecialCharFilter:
    def setup_method(self):
        self.filter = SpecialCharFilter()

    def test_normal_text_unchanged(self):
        text = "This is normal text with punctuation!"
        result = self.filter.clean(text)
        assert result == text

    def test_removes_null_bytes(self):
        text = "Hello\x00World"
        result = self.filter.clean(text)
        assert "\x00" not in result
        assert "HelloWorld" == result

    def test_preserves_newlines(self):
        text = "Line one\nLine two"
        result = self.filter.clean(text)
        assert "\n" in result

    def test_preserves_tabs(self):
        text = "Column one\tColumn two"
        result = self.filter.clean(text)
        assert "\t" in result

    def test_removes_control_characters(self):
        text = "Clean\x01\x02\x03text"
        result = self.filter.clean(text)
        assert "\x01" not in result
        assert "\x02" not in result
        assert "Cleantext" == result
