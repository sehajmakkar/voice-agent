import pytest

from swar.config import Settings


def test_missing_key_gives_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError, match="DEEPGRAM_API_KEY is not set"):
        settings.require("deepgram_api_key")


def test_key_read_from_env_and_hidden_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test-123")
    settings = Settings(_env_file=None)
    assert settings.require("deepgram_api_key") == "dg-test-123"
    assert "dg-test-123" not in repr(settings)  # secrets never leak into logs


async def test_async_tests_run() -> None:
    """Confirms pytest-asyncio is wired up (asyncio_mode = auto)."""
    import asyncio

    await asyncio.sleep(0)
