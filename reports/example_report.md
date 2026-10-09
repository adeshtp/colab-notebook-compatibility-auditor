# Example report

Regenerate with `python scripts/generate_example_report.py`. This report is produced by the same three functions the Streamlit app calls (`rules.audit_notebook`, `explainer.collect_evidence`, `explainer.explain`), run against a committed test fixture. No private notebook content or API key is included.

- Notebook: `tests/fixtures/unpinned_package.ipynb` (committed test fixture)
- Runtime snapshot: `2026.07`
- Provider: `groq` / `openai/gpt-oss-20b`
- LLM calls: 1
- Generated: 2026-10-09

## Notebook summary

- Detected dependencies: 1
- Findings: 2
- **Overall status: ATTENTION**
- Runtime: Ubuntu 22.04.5 LTS, Python 3.12.13, commit `ec53f93fe44a9cab118dc5451527b18e36e1a643`

## Deterministic findings

Produced by `src/rules.py`. Authoritative, and unchanged by the model.

| rule | package | severity | status | cell | message |
|---|---|---|---|---|---|
| R002 | opendatasets | ATTENTION | RISK | 0 | Notebook installs opendatasets with no exact version pin (opendatasets). The runtime version it resolves to is not guaranteed to be stable. |
| R004 | opendatasets | UNKNOWN | UNKNOWN | 0 | opendatasets is not listed in the selected runtime snapshot. Installing it at runtime may be required. Verify manually; snapshot data can lag a live runtime. |

## Retrieved evidence

Official Colab sources, grouped per rule. Retrieval is deterministic.

### R002

**Frequently Asked Questions - Past Runtime Versions** — Google Colab  
<https://research.google.com/colaboratory/runtime-version-faq.html>  
```text
recommends using the latest runtime version, which all notebooks are
configured to do by default, and adding code to a notebook to install specific versions
of libraries that are needed. However, some users may prefer to pin their runtime to a
past version. Stated reasons include:
- The notebook is used by a wide audience, such as in a class or workshop, and the
 author wants to ensure that Colab updates do not break the notebook.
- Colab updates a core dependency that cannot be changed back, such as the Python version.
## Caveats of pinning to a past runtime version
Quoted from the FAQ:
-
```

**Google Colab Adds More Back to School Improvements!** — Google Developers Blog (Google Colab team)  
<https://developers.googleblog.com/en/google-colab-adds-more-back-to-school-improvements/>  
```text
tools and
safe environments, it can lead to challenges when you need to reproduce a specific
result created on an older runtime. With ongoing updates, core dependencies might
change, breaking your code in subtle or significant ways."
And:
"If you've ever tried to re-run a notebook from a few months ago and been met with a
wall of dependency or compatibility errors, you know the frustration of a broken Runtime
environment. ... Reproducibility is a major challenge in the notebook world, especially
for course material."
## Why pinning exists
Quoted: "starting today, you can pin your notebook to
```

**Frequently Asked Questions - Past Runtime Versions** — Google Colab  
<https://research.google.com/colaboratory/runtime-version-faq.html>  
```text
runtime versions are available for 1 year after their release."
## Published runtime versions and their headline components
As listed on the page when retrieved on 2026-10-08. Treat these as a summary; the exact
package set is authoritative only in `googlecolab/backend-info`.
### 2026.07
Ubuntu 22.04.5 LTS; Python 3.12.13; numpy 2.0.2; PyTorch 2.11.0; Jax 0.7.2;
TensorFlow 2.20.0 (not included in TPU runtimes); R 4.6.0; julia 1.12.6
### 2026.04
Ubuntu 22.04.5 LTS; Python 3.12.13; numpy 2.0.2; PyTorch 2.10.0; Jax 0.7.2;
TensorFlow 2.19.0 (not included in TPU runtimes); R 4.5.3; julia 1.11.5
```

### R004

**Frequently Asked Questions - Past Runtime Versions** — Google Colab  
<https://research.google.com/colaboratory/runtime-version-faq.html>  
```text
"It can take 2-3 minutes to connect to a past runtime version, instead of the few
 seconds it takes to connect to a default runtime. This is because we need to download
 the past version image and restart the runtime."
- "Some newer Colab features that rely on newer changes to the runtime may not work with
 past runtime versions."
## How do I use a past runtime version?
Quoted: "You can use a past runtime version by selecting it from the Runtime -> Change
runtime type dialog, with the 'Runtime Version' dropdown."
## How long does a past runtime version stay available?
Quoted: "Currently, past
```

**Backend Information README** — googlecolab/backend-info  
<https://github.com/googlecolab/backend-info/blob/main/README.md>  
```text
but rather the state as of the most recent submitted changes.
There may be a one or two day delay to see the changes in Colab runtimes."
Consequence for this auditor: a package absent from a snapshot's `pip-freeze.txt` is
not proof of absence from a live runtime. This caveat must appear in every generated
report.
## Snapshot-to-commit mapping
The README maps each published runtime version to a specific commit rather than
relying on moving branch names. Commits verified reachable on 2026-10-08:
| Runtime version | backend-info commit |
|---|---|
| 2026.07 |
```

**Frequently Asked Questions - Past Runtime Versions** — Google Colab  
<https://research.google.com/colaboratory/runtime-version-faq.html>  
```text
---
source_id: colab-runtime-version-faq
source: Google Colab
title: "Frequently Asked Questions - Past Runtime Versions"
url: https://research.google.com/colaboratory/runtime-version-faq.html
retrieved: 2026-10-08
runtime_context: all
content_type: SOURCE_FACT
---
## What is a Runtime Version?
Colab runtimes come with many libraries, packages, and binaries pre-installed. Colab
updates these frequently in order to provide users with new capabilities and bug fixes.
Runtime Versions refer to past versions of the Colab runtime.
## Why would I want to use a past runtime version?
Google generally
```

## AI-generated explanation

Model prose only. It cannot change any field in the table above.

**Summary**

The notebook unpinned opendatasets and runs on a 2026.07 snapshot that does not list it. This may lead to unresolved package installs or version drift.

**Explanations**

- R002: The notebook installs opendatasets without a version pin, so the runtime resolves to an unguaranteed version that may change.
- R004: opendatasets is not listed in the selected runtime snapshot, so installing it at runtime may be required; snapshot data can lag a live runtime.

**Recommended manual checks**

- Check that opendatasets is installed after notebook execution.
- Verify the resolved opendatasets version.
- Confirm that the runtime snapshot includes all other required libraries.

Rules not explained by the model: none

## Limitations

- The notebook is analysed, never executed.
- `READY` means no issue was detected by the supported checks, not that the notebook runs.
- Runtime snapshots are published CI data and can lag the live runtime.
- The AI explanation is secondary and can be wrong; the deterministic findings stand alone.
