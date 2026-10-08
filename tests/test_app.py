"""Tests for the Streamlit UI.

These drive the real app with Streamlit's AppTest rather than asserting on helper
functions. The behaviour that matters is the degraded path: the deterministic audit
and evidence retrieval must still work when no provider key is available.
"""

import sys
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app" / "streamlit_app.py"
FIXTURES = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(ROOT / "src"))


def open_app() -> AppTest:
    """Load and first-run the app so its widgets exist in the element tree."""
    return AppTest.from_file(str(APP_PATH), default_timeout=600).run()


def upload(app: AppTest, fixture: str) -> AppTest:
    path = FIXTURES / f"{fixture}.ipynb"
    app.file_uploader[0].upload(path.name, path.read_bytes()).run()
    return app


def analyse(app: AppTest) -> AppTest:
    app.button[0].click().run()
    return app


@pytest.fixture(scope="module")
def loaded_app():
    return open_app()


def test_app_loads_without_crashing(loaded_app):
    assert not loaded_app.exception


def test_no_key_still_produces_the_deterministic_audit(monkeypatch):
    """The most important guarantee: the audit survives without an API key."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = analyse(upload(open_app(), "mismatching_pin"))

    assert not app.exception
    text = " ".join(item.value for item in app.markdown)
    assert "HIGH_RISK" in text
    assert "R001" in text


def test_no_key_reports_the_ai_step_as_unavailable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = analyse(upload(open_app(), "mismatching_pin"))

    body = " ".join([info.value for info in app.info] + [w.value for w in app.warning])
    assert "not configured" in body or "unavailable" in body


def test_locked_provider_models_match_the_decision():
    source = APP_PATH.read_text()

    assert '"groq": "openai/gpt-oss-20b"' in source
    assert '"ollama": "ministral-3:3b"' in source


def test_app_source_contains_no_secret_values():
    source = APP_PATH.read_text()

    assert "gsk_" not in source
    assert "GROQ_API_KEY=" not in source


def test_app_never_executes_the_notebook():
    """The app must not import, exec or eval notebook content."""
    source = APP_PATH.read_text()

    for forbidden in ("exec(", "eval(", "subprocess", "os.system", "runpy"):
        assert forbidden not in source