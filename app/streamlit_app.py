"""Streamlit UI for the Colab Runtime Knowledge Assistant.

This file contains presentation only. Retrieval decisions live in src/qa.py and
src/knowledge_base.py, the audit decisions live in src/rules.py, and every model call
lives in src/explainer.py. A notebook is read as JSON and is never executed.

Two independent modes share one knowledge base:

  * Ask       - the primary mode. A question is embedded, passages are retrieved from
                the curated sources, and the provider answers using only those passages.
  * Audit     - the secondary mode. Deterministic R001-R006 findings, evidence to
                explain them, and one optional AI explanation of an existing result.

Neither mode feeds the other. Questions never touch the rule engine, and a finding is
never produced from a model response.
"""

import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import notebook_parser  # noqa: E402
import runtime_checker  # noqa: E402
from explainer import (  # noqa: E402
    ProviderError,
    collect_evidence,
    explain,
    unexplained_rules,
)
from knowledge_base import build_knowledge, ingest  # noqa: E402
import qa  # noqa: E402
import rules  # noqa: E402

# Locked provider decision, see AI_PROVIDER.md. The same provider serves both modes.
PROVIDER_MODELS = {
    "groq": "openai/gpt-oss-20b",
    "ollama": "ministral-3:3b",
}
KEY_VARIABLES = {"groq": "GROQ_API_KEY"}

STATUS_COLOUR = {"READY": "green", "ATTENTION": "orange", "HIGH_RISK": "red", "UNKNOWN": "grey"}

st.set_page_config(page_title="Colab Runtime Knowledge Assistant", layout="wide")


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


def plural(count: int, singular: str, many: str) -> str:
    """'1 dependency' reads better than '1 dependencies'."""
    return f"{count} {singular if count == 1 else many}"


def render_passages(passages: list[dict], heading: str = "Retrieved passages") -> None:
    """Show retrieved chunks with their real source references.

    Several retrieved chunks usually come from one document, so they are grouped
    under a single heading and the source is stated once instead of per chunk.
    Quoted source text is rendered literally: passing it through st.markdown would
    interpret the document's own headings and turn evidence into page headings.
    """
    st.markdown(f"**{heading}**")

    if not passages:
        st.info("No passages were retrieved.")
        return

    by_source: dict[tuple, list[str]] = {}
    for passage in passages:
        key = (passage["source"], passage["title"], passage["url"], passage["source_id"])
        by_source.setdefault(key, []).append(passage["content"])

    for (source, title, url, source_id), snippets in by_source.items():
        st.markdown(f"*{source} — {title}*")
        st.caption(f"{url}  ·  `{source_id}`")
        for snippet in snippets:
            st.text(snippet)


def render_answered(
    result: qa.Answered,
    provider: str,
    model: str,
    disabled_note: str | None = None,
) -> None:
    """Render one answered question, including every failure state."""
    if result.status == "empty_question":
        st.info("Type a question to search the curated Colab documentation.")
        return

    st.caption(
        f"{plural(len(result.passages), 'passage', 'passages')} retrieved · "
        f"evidence coverage {result.coverage:.2f} of {qa.MIN_EVIDENCE_COVERAGE:.2f} required"
    )

    if result.status == "no_passages":
        st.warning(
            "Retrieval returned nothing from the curated corpus, so there is no "
            "evidence to answer from."
        )
        return

    if result.status == "insufficient_evidence":
        st.error("**The curated documentation does not appear to cover this question.**")
        st.markdown(
            "The passages below were the nearest matches in the corpus, but they do "
            "not discuss this topic. The assistant will not answer from them, and it "
            "has not called the model at all. This is a deliberate refusal, not a "
            "failure."
        )
        st.caption(result.detail)
        render_passages(result.passages)
        return

    if result.status == "disabled":
        st.info(
            disabled_note
            or "No answer was generated. The retrieved passages are shown below so you "
            "can read the source material directly."
        )
        render_passages(result.passages)
        return

    if result.status == "failed":
        st.error("The provider call failed. The retrieved passages are shown below.")
        if result.detail:
            st.caption(f"Reason: {result.detail}")
        render_passages(result.passages)
        return

    # ---------------------------------------------------------------- answered
    answer = result.answer

    st.markdown(answer.answer)

    st.caption(f"Provider: {provider} · model: {model} · one model call completed.")

    if result.unsupported_citations:
        st.warning(
            "The model cited a source that was not in the retrieved set, so it is not "
            f"shown as a reference here: {', '.join(result.unsupported_citations)}"
        )

    st.markdown("**Sources used**")
    if not result.used_sources:
        st.info(
            "The model did not attribute the answer to any of the retrieved passages. "
            "Read the passages below before relying on it."
        )
    # Several passages can come from one document, so list each source once.
    listed = set()
    for passage in result.passages:
        if passage["source_id"] in result.used_sources and passage["source_id"] not in listed:
            listed.add(passage["source_id"])
            st.markdown(f"- [{passage['title']}]({passage['url']}) — {passage['source']}")

    if answer.caveats:
        st.markdown("**Limits of the retrieved evidence**")
        for item in answer.caveats:
            st.markdown(f"- {item}")

    if answer.follow_ups:
        st.markdown("**Related questions this corpus could answer**")
        for item in answer.follow_ups:
            st.markdown(f"- {item}")

    render_passages(result.passages)


st.title("Colab Runtime Knowledge Assistant")
st.caption(
    "Ask a question about Colab runtimes and dependency compatibility, and get an "
    "answer grounded in retrieved official documentation."
)

with st.expander("What this is, and what it is not"):
    st.markdown(
        "It answers questions using **only** passages retrieved from five curated "
        "official Google Colab documents held in this repository. If those passages do "
        "not cover the question, it says so and stops.\n\n"
        "- It does not use outside knowledge. If the answer is not in the retrieved "
        "passages, it is not in the answer.\n"
        "- It does not execute notebooks. Uploaded notebooks are read as JSON only.\n"
        "- `READY` in the audit tab means no obvious risk was found by the implemented "
        "checks. It does **not** guarantee a notebook will run."
    )

provider = st.sidebar.selectbox("Model provider", list(PROVIDER_MODELS))
model = PROVIDER_MODELS[provider]
if provider == "ollama":
    st.sidebar.caption("Offline local mode. No API key required.")
else:
    st.sidebar.caption(f"Reads {KEY_VARIABLES[provider]} from Streamlit secrets or the environment.")
st.sidebar.caption(
    "Retrieval, embeddings and the vector database all run locally. Only answer "
    "generation calls a provider."
)

api_key = resolve_api_key(provider)

ask_tab, audit_tab = st.tabs(["Ask a question", "Audit a notebook"])

# ============================================================== ask a question
with ask_tab:
    question = st.text_input(
        "Your question",
        placeholder="How do I pin a notebook to a past Colab runtime version?",
        key="ask_question",
        help="Searched against the curated official Colab documentation only.",
    )
    top_k = st.slider(
        "Passages to retrieve",
        min_value=1,
        max_value=8,
        value=qa.DEFAULT_TOP_K,
        key="ask_top_k",
    )
    ask_ai = st.checkbox(
        "Generate a written answer",
        value=True,
        key="ask_ai",
        help="Retrieval and the evidence check always run, whether or not this is on.",
    )

    if st.button("Ask", type="primary", key="ask_submit"):
        # Retrieval and the evidence check always run, with or without a provider.
        # Only answer generation needs the key, so the gate's verdict is reported
        # either way and a keyless user still sees the source material.
        disabled_note = None
        if not api_key:
            disabled_note = (
                f"No written answer was generated because "
                f"{KEY_VARIABLES.get(provider, 'the provider key')} is not configured. "
                "The retrieved passages are shown below so you can read the source "
                "material directly. Set the key as a Streamlit secret or an environment "
                "variable to enable written answers."
            )

        answered = qa.answer_question(
            get_knowledge(),
            question,
            provider=provider,
            model=model,
            top_k=top_k,
            use_ai=ask_ai and bool(api_key),
        )
        render_answered(answered, provider, model, disabled_note=disabled_note)

# =========================================================== audit a notebook
with audit_tab:
    uploaded = st.file_uploader("Colab notebook (.ipynb)", type=["ipynb"], key="audit_upload")
    snapshot = st.selectbox(
        "Colab runtime snapshot",
        runtime_checker.list_snapshots(),
        key="audit_snapshot",
        help="Package metadata vendored from googlecolab/backend-info at a pinned commit.",
    )
    use_ai = st.checkbox(
        "Generate AI explanation",
        value=True,
        key="audit_ai",
        help="One model call per audit. The findings below never depend on it.",
    )

    analyse_clicked = st.button(
        "Analyze", type="primary", disabled=uploaded is None, key="audit_analyze"
    )

    if analyse_clicked:
        # The uploaded notebook is written to a private temp file so the existing
        # parser can read it as JSON. A unique name per session stops two concurrent
        # users from overwriting each other's notebook, and it is deleted immediately.
        if uploaded.size > notebook_parser.MAX_NOTEBOOK_BYTES:
            st.error(
                f"File is too large to parse safely. Limit is "
                f"{notebook_parser.MAX_NOTEBOOK_BYTES // (1024 * 1024)} MB."
            )
        else:
            handle = tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False)
            upload_path = Path(handle.name)
            try:
                handle.write(uploaded.getbuffer())
                handle.close()
                try:
                    result = rules.audit_notebook(str(upload_path), snapshot)
                except Exception:
                    st.error("This file could not be read as a Jupyter notebook.")
                    result = None
            finally:
                upload_path.unlink(missing_ok=True)

            if result is not None:
                # The parser reads the notebook name off the path, and the temp name
                # is random, so restore the name the user actually uploaded.
                result.notebook_name = uploaded.name

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

                st.divider()
                st.subheader("Overall status")
                st.markdown(f"### :{STATUS_COLOUR.get(result.status, 'grey')}[{result.status}]")

                summary_bits = [
                    f"Notebook `{result.notebook_name}`",
                    f"runtime {result.runtime.snapshot}"
                    if result.runtime
                    else "no runtime selected",
                ]
                if result.runtime:
                    summary_bits.append(
                        f"{result.runtime.os_version}, Python {result.runtime.python_version}"
                    )
                summary_bits.append(plural(len(result.dependencies), "dependency", "dependencies"))
                summary_bits.append(plural(len(result.findings), "finding", "findings"))
                st.caption(" · ".join(str(bit) for bit in summary_bits))

                st.subheader("Detected by auditor")
                st.caption(
                    "Produced by the rule engine in `src/rules.py`. These fields are "
                    "authoritative and are never written by a model."
                )

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
                        width="stretch",
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
                st.caption(
                    "Official Colab sources, shown before the AI text so the source "
                    "material is visible. Retrieved to explain the findings above."
                )

                if not evidence:
                    st.info("No rules fired, so no evidence was retrieved.")

                for rule, hits in evidence.items():
                    st.markdown(f"**{rule}**")
                    if not hits:
                        st.warning("No evidence retrieved for this rule.")
                    render_passages(hits)

                st.subheader("AI-generated explanation")
                st.caption(f"Provider: {provider} · model: {model} · {status_caption(llm_status)}.")

                if explanation is None:
                    if llm_status == "disabled":
                        st.info("AI explanation was not requested.")
                    elif llm_status == "not_configured":
                        st.info(
                            "AI explanation unavailable because the provider is not "
                            f"configured. Set {KEY_VARIABLES.get(provider, 'the provider key')} "
                            "as a Streamlit secret or an environment variable. The "
                            "deterministic audit above is unaffected."
                        )
                    else:
                        st.warning(
                            "AI explanation unavailable. Deterministic audit completed "
                            "successfully."
                        )
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
                    "- `READY` means no obvious risk was detected by the implemented "
                    "checks. It does **not** guarantee the notebook will execute.\n"
                    "- Package metadata comes from published CI snapshots and can lag a "
                    "live runtime.\n"
                    "- Parsing is regex based, so an import inside a comment can be read "
                    "as a dependency.\n"
                    "- A package absent from the snapshot is reported as `UNKNOWN`, never "
                    "as a failure.\n"
                    "- Import names are mapped to distribution names by a short fixed "
                    "list, so an unmapped mismatch is reported as an absent package."
                )

                if explanation is not None and explanation.limitations:
                    st.markdown("**Reported by the model**")
                    for item in explanation.limitations:
                        st.markdown(f"- {item}")