"""Tests for Settings.from_env() — specifically bind-host validation."""

from __future__ import annotations

import pytest


class TestBindHostValidation:
    """Settings.from_env() must reject non-loopback hosts unless opted in."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        """Remove host/port/expose vars before each test."""
        for var in (
            "PATHLY_FSM_HTTP_HOST",
            "PATHLY_FSM_HTTP_PORT",
            "PATHLY_EXPOSE_HOST",
        ):
            monkeypatch.delenv(var, raising=False)

    # ------------------------------------------------------------------ #
    # Loopback addresses — always allowed, no opt-in needed               #
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("loopback", ["127.0.0.1", "::1", "localhost"])
    def test_loopback_accepted(self, monkeypatch, loopback):
        monkeypatch.setenv("PATHLY_FSM_HTTP_HOST", loopback)
        from pathly_orchestrator.config import Settings

        s = Settings.from_env()
        assert s.host == loopback

    def test_default_is_loopback(self):
        """With no env var the default 127.0.0.1 must be accepted silently."""
        from pathly_orchestrator.config import Settings

        s = Settings.from_env()
        assert s.host == "127.0.0.1"

    # ------------------------------------------------------------------ #
    # Non-loopback without opt-in → must exit                            #
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        "addr", ["0.0.0.0", "192.168.1.100", "10.0.0.1", "0.0.0.0"]
    )
    def test_non_loopback_without_expose_exits(self, monkeypatch, addr):
        monkeypatch.setenv("PATHLY_FSM_HTTP_HOST", addr)
        with pytest.raises(SystemExit) as exc_info:
            from pathly_orchestrator.config import Settings

            Settings.from_env()
        assert exc_info.value.code == 1

    @pytest.mark.parametrize("addr", ["0.0.0.0", "192.168.1.100", "10.0.0.1"])
    def test_non_loopback_without_expose_prints_error(self, monkeypatch, capsys, addr):
        monkeypatch.setenv("PATHLY_FSM_HTTP_HOST", addr)
        with pytest.raises(SystemExit):
            from pathly_orchestrator.config import Settings

            Settings.from_env()
        err = capsys.readouterr().err
        assert "non-loopback" in err.lower() or "ERROR" in err
        assert "PATHLY_EXPOSE_HOST" in err

    # ------------------------------------------------------------------ #
    # Non-loopback WITH opt-in → allowed, but must warn                  #
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize("addr", ["0.0.0.0", "192.168.1.100"])
    def test_non_loopback_with_expose_allowed(self, monkeypatch, addr):
        monkeypatch.setenv("PATHLY_FSM_HTTP_HOST", addr)
        monkeypatch.setenv("PATHLY_EXPOSE_HOST", "true")
        from pathly_orchestrator.config import Settings

        s = Settings.from_env()
        assert s.host == addr

    @pytest.mark.parametrize("addr", ["0.0.0.0", "192.168.1.100"])
    def test_non_loopback_with_expose_prints_warning(self, monkeypatch, capsys, addr):
        monkeypatch.setenv("PATHLY_FSM_HTTP_HOST", addr)
        monkeypatch.setenv("PATHLY_EXPOSE_HOST", "true")
        from pathly_orchestrator.config import Settings

        Settings.from_env()
        err = capsys.readouterr().err
        assert "WARNING" in err
        assert "/events/" in err  # must mention the unauthenticated surface

    def test_expose_false_string_still_blocks(self, monkeypatch):
        """PATHLY_EXPOSE_HOST=false must NOT be treated as opt-in."""
        monkeypatch.setenv("PATHLY_FSM_HTTP_HOST", "0.0.0.0")
        monkeypatch.setenv("PATHLY_EXPOSE_HOST", "false")
        with pytest.raises(SystemExit) as exc_info:
            from pathly_orchestrator.config import Settings

            Settings.from_env()
        assert exc_info.value.code == 1

    def test_expose_true_case_insensitive(self, monkeypatch):
        """PATHLY_EXPOSE_HOST=TRUE (uppercase) must still be accepted."""
        monkeypatch.setenv("PATHLY_FSM_HTTP_HOST", "0.0.0.0")
        monkeypatch.setenv("PATHLY_EXPOSE_HOST", "TRUE")
        from pathly_orchestrator.config import Settings

        s = Settings.from_env()
        assert s.host == "0.0.0.0"
