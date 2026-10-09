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
    app.file_uploader(key="audit_upload").upload(path.name, path.read_bytes()).run()
    return app


def analyse(app: AppTest) -> AppTest:
    app.button(key="audit_analyze").click().run()
    return app


def ask(app: AppTest, question: str) -> AppTest:
    """Type a question into the QA tab and submit it."""
    app.text_input(key="ask_question").set_value(question).run()
    app.button(key="ask_submit").click().run()
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


def test_report_names_the_uploaded_notebook_not_the_temp_file(monkeypatch):
    """The report must show the user's filename, never a random temp name."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = analyse(upload(open_app(), "mismatching_pin"))

    captions = " ".join(c.value for c in app.caption)
    assert "mismatching_pin.ipynb" in captions
    assert "tmp" not in captions.split("mismatching_pin.ipynb")[0][-40:]


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


# ------------------------------------------------------------- question asking

def test_question_mode_retrieves_and_shows_sources_without_a_key(monkeypatch):
    """The primary mode must work with no provider key at all."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = ask(open_app(), "Where is Google Drive mounted in a Colab runtime?")

    assert not app.exception
    body = " ".join([c.value for c in app.caption] + [m.value for m in app.markdown])
    assert "colab-filesystem-conventions" in body
    assert "research.google.com" in body or "google-colab-cli" in body


def test_question_mode_refuses_when_the_corpus_does_not_cover_it(monkeypatch):
    """A question the corpus cannot answer must show a refusal, not an invented answer."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = ask(open_app(), "How much RAM does a free Colab runtime give me?")

    assert not app.exception
    errors = " ".join(e.value for e in app.error)
    assert "does not appear to cover this question" in errors


def test_question_mode_reports_the_coverage_it_measured(monkeypatch):
    """The gate's number is shown, so a refusal is inspectable rather than magic."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = ask(open_app(), "Where is Google Drive mounted in a Colab runtime?")

    captions = " ".join(c.value for c in app.caption)
    assert "evidence coverage" in captions


def test_blank_question_is_handled(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = ask(open_app(), "")

    assert not app.exception
    assert any("Type a question" in i.value for i in app.info)


def test_both_modes_coexist(monkeypatch):
    """The audit tab must keep working in the same app as the QA tab."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    app = analyse(upload(open_app(), "unpinned_package"))

    text = " ".join(item.value for item in app.markdown)
    assert "ATTENTION" in text
    assert "R002" in text
    assert "R004" in text


def test_audit_findings_are_not_overwritable_through_the_question_path():
    """A question cannot inject a finding. The rule engine owns those fields."""
    source = APP_PATH.read_text()

    # The QA tab must not call the rule engine at all.
    ask_section = source.split('with ask_tab:')[1].split('with audit_tab:')[0]
    assert "rules." not in ask_section
    assert "audit_notebook" not in ask_section