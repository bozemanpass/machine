"""Tests for graceful handling of cloud provider API errors (#95).

These are hermetic: instead of making real API calls they drive the
``cli`` entry-point wrapper directly, forcing the underlying Click group to
raise the same exceptions a provider SDK would raise on an auth failure.
"""

import digitalocean
import pytest

from machine import main as main_module
from machine.types import CliOptions


@pytest.fixture(autouse=True)
def reset_options():
    """Ensure the global CLI options don't leak between tests."""
    saved = main_module.d.opt
    main_module.d.opt = None
    yield
    main_module.d.opt = saved


class TestFriendlyProviderError:
    def test_auth_failure_message_is_actionable(self):
        msg = main_module._friendly_provider_error(digitalocean.DataReadError("Unable to authenticate you"))
        assert "unauthenticated or unauthorized" in msg
        assert "config file" in msg
        # The scary raw exception text should not leak into the friendly message.
        assert "DataReadError" not in msg

    def test_non_auth_failure_includes_detail(self):
        msg = main_module._friendly_provider_error(digitalocean.DataReadError("Rate limit exceeded"))
        assert "Rate limit exceeded" in msg
        assert "cloud provider request failed" in msg


class TestCliWrapper:
    def _run_cli(self, monkeypatch, exc):
        def boom():
            raise exc

        monkeypatch.setattr(main_module, "main", boom)
        return main_module.cli

    def test_auth_error_produces_message_not_traceback(self, monkeypatch, capsys):
        run = self._run_cli(monkeypatch, digitalocean.DataReadError("Unable to authenticate you"))
        with pytest.raises(SystemExit) as exc_info:
            run()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "unauthenticated or unauthorized" in err
        assert "Traceback" not in err

    def test_debug_flag_reraises_original_exception(self, monkeypatch):
        main_module.d.opt = CliOptions(debug=True, quiet=False, verbose=False, dry_run=False)
        run = self._run_cli(monkeypatch, digitalocean.DataReadError("Unable to authenticate you"))
        with pytest.raises(digitalocean.DataReadError):
            run()

    def test_non_provider_exception_is_not_swallowed(self, monkeypatch):
        run = self._run_cli(monkeypatch, ValueError("some internal bug"))
        with pytest.raises(ValueError):
            run()
