"""Streamlit UI for the Colab Notebook Compatibility Auditor.

This file contains presentation only. Every audit decision lives in src/rules.py and
every model call lives in src/explainer.py. The notebook is read as JSON and is never
executed.
"""

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import runtime_checker  # noqa: E402
from explainer import (  # noqa: E402
    ProviderError,
    collect_evidence,
    explain,
    unexplained_rules,
)
from knowledge_base import build_knowledge, ingest  # noqa: E402
import rules  # noqa: E402

# Locked provider decision, see AI_PROVIDER.md.
PROVIDER_MODELS = {
    "groq": "openai/gpt-oss-20b",
    "ollama": "ministral-3:3b",
}
KEY_VARIABLES = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}

STATUS_COLOUR = {"READY": "green", "ATTENTION": "orange", "HIGH_RISK": "red", "UNKNOWN": "grey"}

st.set_page_config(page_title="Colab Notebook Compatibility Auditor", layout="wide")


@st.cache_resource(show_spinner="Building local knowledge base from curated sources...")
def get_knowledge():
    """Build the LanceDB index once per Streamlit session.

    rebuild=True on purpose. A Streamlit Community Cloud filesystem is not durable,
    so the index is always recreated from the five committed curated sources rather
    than assuming a previously generated database still exists.
    """
    knowledge = build_knowledge(rebuild=True)
    ingest(knowledge)
    return knowledge


def resolve_api_key(provider: str) -> str | None:
    """Return the provider key from Streamlit secrets or the environment.

    Returns None when absent. The value is never displayed or logged. When the key
    comes from Streamlit secrets it is copied into the environment because the
    provider SDKs read it from there.
    """
    variable = KEY_VARIABLES.get(provider)
    if variable is None:
        return "local"

    try:
        if variable in st.secrets:
            value = st.secrets[variable]
            os.environ[variable] = str(value)
            return str(value)
    except Exception:
        # No secrets file present, which is normal for a local run.
        pass

    return os.environ.get(variable)


def status_caption(llm_status: str) -> str:
    """One line describing the provider outcome, safe to show a normal user."""
    return {
        "ok": "one model call completed",
        "disabled": "not requested",
        "not_configured": "provider not configured",
        "failed": "provider call failed",
    }.get(llm_status, llm_status)


st.title("Colab Notebook Compatibility Auditor")
st.caption(
    "Deterministic notebook auditing, then retrieval of official Colab evidence, "
    "then one AI explanation call."
)

with st.expander("What this tool does not do"):
    st.markdown(
        "- It does not execute the notebook. The file is read as JSON only.\n"
        "- It does not decide whether a compatibility problem exists. The rules do.\n"
        "- It does not repair anything or solve dependencies.\n"
        "- `READY` means no obvious risk was detected by the implemented checks. "
        "It does **not** guarantee the notebook will run."
    )

provider = st.sidebar.selectbox("Explanation provider", list(PROVIDER_MODELS))
model = PROVIDER_MODELS[provider]
if provider == "ollama":
    st.sidebar.caption("Offline local mode. No API key required.")
else:
    st.sidebar.caption(f"Reads {KEY_VARIABLES[provider]} from Streamlit secrets or the environment.")

uploaded = st.file_uploader("Colab notebook (.ipynb)", type=["ipynb"])
snapshot = st.selectbox(
    "Colab runtime snapshot",
    runtime_checker.list_snapshots(),
    help="Package metadata vendored from googlecolab/backend-info at a pinned commit.",
)
use_ai = st.checkbox("Generate AI explanation", value=True,
                     help="One model call per audit. The findings below never depend on it.")

if not st.button("Analyze", type="primary", disabled=uploaded is None):
    st.stop()

api_key = resolve_api_key(provider)

# The notebook is written to disk only so the existing parser can read it as JSON.
upload_path = Path("/tmp") / "colab_audit_upload.ipynb"
upload_path.write_bytes(uploaded.getbuffer())

try:
    result = rules.audit_notebook(str(upload_path), snapshot)
except Exception:
    st.error("This file could not be read as a Jupyter notebook.")
    st.stop()

knowledge = get_knowledge()
evidence = collect_evidence(knowledge, result)

explanation = None
llm_status = "disabled"
llm_error = ""

if use_ai and api_key:
    try:
        explanation = explain(result, evidence, provider=provider, model=model)
        llm_status = "ok"
    except ProviderError as exc:
        llm_status, llm_error = "failed", str(exc)
    except Exception as exc:
        llm_status, llm_error = "failed", type(exc).__name__
elif use_ai:
    llm_status = "not_configured"

# ------------------------------------------------------------------ report
st.subheader("Overall status")
st.markdown(f"### :{STATUS_COLOUR.get(result.status, 'grey')}[{result.status}]")

summary_bits = [
    f"Notebook `{result.notebook_name}`",
    f"runtime **{result.runtime.snapshot}"
    if result.runtime else "no runtime selected",
]
if result.runtime:
    summary_bits.append(
        f"{result.runtime.os_version}, Python {result.runtime.python_version}"
    )
summary_bits.append(f"{len(result.dependencies)} dependencies")
summary_bits.append(f"{len(result.findings)} findings")
st.caption(" · ".join(str(bit) for bit in summary_bits))

st.subheader("Detected by auditor")
st.caption("Produced by the rule engine in `src/rules.py`. These fields are authoritative.")

if result.dependencies:
    st.dataframe(
        [
            {
                "package": item.name,
                "version": item.version or "",
                "as written": item.raw,
                "cell": item.cell,
                "found via": item.origin,
            }
            for item in result.dependencies
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No package references were detected in this notebook.")

if not result.findings:
    st.success("No findings from the implemented checks.")

for finding in result.findings:
    label = f"{finding.rule} · {finding.package or 'notebook'} — {finding.severity}"
    with st.expander(label, expanded=True):
        st.write(f"**Severity:** {finding.severity}")
        st.write(f"**Status:** {finding.status}")
        if finding.cell is not None:
            st.write(f"**Cell:** {finding.cell}")
        st.write(finding.message)

st.subheader("Retrieved evidence")
st.caption("Official Colab sources, shown before the AI text so the source material is visible.")

if not evidence:
    st.info("No rules fired, so no evidence was retrieved.")

for rule, hits in evidence.items():
    st.markdown(f"**{rule}**")
    if not hits:
        st.warning("No evidence retrieved for this rule.")
    for hit in hits:
        with st.expander(f"{hit['title']} — {hit['source']}"):
            st.caption(hit["url"])
            st.text(hit["content"])

st.subheader("AI-generated explanation")
st.caption(f"Provider: {provider} · model: {model} · {status_caption(llm_status)}.")

if explanation is None:
    if llm_status == "disabled":
        st.info("AI explanation was not requested.")
    elif llm_status == "not_configured":
        st.info(
            "AI explanation unavailable because the provider is not configured. "
            f"Set {KEY_VARIABLES.get(provider, 'the provider key')} as a Streamlit secret "
            "or an environment variable. The deterministic audit above is unaffected."
        )
    else:
        st.warning("AI explanation unavailable. Deterministic audit completed successfully.")
        if llm_error:
            st.caption(f"Reason: {llm_error}")
else:
    st.write(explanation.summary)

    st.markdown("**Explanations**")
    for item in explanation.explanations:
        st.markdown(f"- {item}")

    st.markdown("**Recommended manual checks**")
    for item in explanation.recommendations:
        st.markdown(f"- {item}")

    missing = unexplained_rules(result, explanation)
    if missing:
        st.warning(f"The model did not explain: {', '.join(missing)}.")

st.subheader("Limitations")
st.markdown(
    "- `READY` means no obvious risk was detected by the implemented checks. It does "
    "**not** guarantee the notebook will execute.\n"
    "- Package metadata comes from published CI snapshots and can lag a live runtime.\n"
    "- Parsing is regex based, so an import inside a comment can be read as a dependency.\n"
    "- A package absent from the snapshot is reported as `UNKNOWN`, never as a failure.\n"
    "- Import names are mapped to distribution names by a short fixed list, so an "
    "unmapped mismatch is reported as an absent package."
)

if explanation is not None and explanation.limitations:
    st.markdown("**Reported by the model**")
    for item in explanation.limitations:
        st.markdown(f"- {item}")