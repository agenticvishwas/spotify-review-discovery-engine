VALID_PLATFORMS = frozenset({"app_store", "google_play", "reddit", "community", "social"})

_PLATFORM_MAP: dict[str, str] = {
    "app_store": "app_store",
    "appstore": "app_store",
    "apple": "app_store",
    "apple_app_store": "app_store",
    "google_play": "google_play",
    "googleplay": "google_play",
    "play_store": "google_play",
    "google": "google_play",
    "reddit": "reddit",
    "community": "community",
    "spotify_community": "community",
    "social": "social",
    "twitter": "social",
    "x": "social",
}


class PlatformMapper:
    """Map raw platform strings to canonical platform enum values."""

    def map(self, platform: str) -> str:
        normalized = platform.lower().replace("-", "_").strip()
        return _PLATFORM_MAP.get(normalized, platform)
