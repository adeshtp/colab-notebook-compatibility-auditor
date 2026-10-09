# Example: question answering

Regenerate with `python scripts/generate_example_qa.py`. Produced by the same `qa.answer_question` the Streamlit question tab calls, against the committed curated corpus. No private data and no API key are included.

- Provider: `groq` / `openai/gpt-oss-20b`
- At most one model call per question
- Evidence threshold: 0.50
- Generated: 2026-10-09

## How do I pin a notebook to a past Colab runtime version?

*Why this question was chosen:* Answerable. colab-runtime-version-faq describes the Runtime -> Change runtime type dialog.

- Status: `ok`
- Passages retrieved: 4
- Evidence coverage: **1.00** (threshold 0.50)

### Answer

To pin a notebook to a past Colab runtime version, open the "Change runtime type" dialog (found under the Runtime menu) and select the desired runtime version from the Runtime Version selector. This locks the notebook to that version so it will run with the same package set each time you open it. The dialog defaults to "Latest", but any listed past version can be chosen to pin the notebook to that snapshot.

### Sources used

- [Google Colab Adds More Back to School Improvements!](https://developers.googleblog.com/en/google-colab-adds-more-back-to-school-improvements/) — Google Developers Blog (Google Colab team)
- [Frequently Asked Questions - Past Runtime Versions](https://research.google.com/colaboratory/runtime-version-faq.html) — Google Colab

### Limits of the retrieved evidence

- Connecting to a past runtime can take 2-3 minutes because the image must be downloaded and the runtime restarted. 
- Some newer Colab features that rely on newer runtime components may not be available when pinning to an older version. 
- Core dependencies such as the Python version are updated in newer runtimes and cannot be rolled back, so pinning may not restore all earlier behavior.

### Retrieved passages

**[1] colab-backend-info-transparency** — Google Colab Adds More Back to School Improvements!  
<https://developers.googleblog.com/en/google-colab-adds-more-back-to-school-improvements/>
```text
compatibility errors, you know the frustration of a broken Runtime
environment. ... Reproducibility is a major challenge in the notebook world, especially
for course material."
## Why pinning exists
Quoted: "starting today, you can pin your notebook to a specific, versioned Colab
runtime. This means you can guarantee that your code will execute in the same runtime
with the same package versions, every time."
The Runtime Version Selector is in the "Change runtime type" dialog. New notebooks
default to the "Latest" version.
## Full transparency with the backend-info GitHub repository
Quoted:
```

**[2] colab-runtime-version-faq** — Frequently Asked Questions - Past Runtime Versions  
<https://research.google.com/colaboratory/runtime-version-faq.html>
```text
reasons include:
- The notebook is used by a wide audience, such as in a class or workshop, and the
 author wants to ensure that Colab updates do not break the notebook.
- Colab updates a core dependency that cannot be changed back, such as the Python version.
## Caveats of pinning to a past runtime version
Quoted from the FAQ:
- "It can take 2-3 minutes to connect to a past runtime version, instead of the few
 seconds it takes to connect to a default runtime. This is because we need to download
 the past version image and restart the runtime."
- "Some newer Colab features that rely on newer
```

**[3] colab-runtime-version-faq** — Frequently Asked Questions - Past Runtime Versions  
<https://research.google.com/colaboratory/runtime-version-faq.html>
```text
## What is a Runtime Version?
Colab runtimes come with many libraries, packages, and binaries pre-installed. Colab
updates these frequently in order to provide users with new capabilities and bug fixes.
Runtime Versions refer to past versions of the Colab runtime.
## Why would I want to use a past runtime version?
Google generally recommends using the latest runtime version, which all notebooks are
configured to do by default, and adding code to a notebook to install specific versions
of libraries that are needed. However, some users may prefer to pin their runtime to a
past version. Stated
```

**[4] colab-backend-info-transparency** — Google Colab Adds More Back to School Improvements!  
<https://developers.googleblog.com/en/google-colab-adds-more-back-to-school-improvements/>
```text
## The challenge of a dynamic runtime
Quoted from the official Google Colab announcement:
"Colab Runtimes are continuously updated with the latest software packages, security
patches, and features. While this ensures you always have access to modern tools and
safe environments, it can lead to challenges when you need to reproduce a specific
result created on an older runtime. With ongoing updates, core dependencies might
change, breaking your code in subtle or significant ways."
And:
"If you've ever tried to re-run a notebook from a few months ago and been met with a
wall of dependency or
```

## Where is Google Drive mounted in a Colab runtime?

*Why this question was chosen:* Answerable. google-colab-cli documents the /content/drive default mount.

- Status: `ok`
- Passages retrieved: 4
- Evidence coverage: **1.00** (threshold 0.50)

### Answer

Google Drive is mounted at the path `/content/drive` in a Colab runtime.

### Sources used

- [Colab CLI README - runtime filesystem and drive mount](https://github.com/googlecolab/google-colab-cli) — googlecolab/google-colab-cli

### Retrieved passages

**[1] colab-filesystem-conventions** — Colab CLI README - runtime filesystem and drive mount  
<https://github.com/googlecolab/google-colab-cli>
```text
This is the authoritative confirmation that a Colab runtime exposes a `/content/`
prefix, and that Drive is conventionally mounted at `/content/drive`.
## Package installation targets the runtime VM
Quoted: "`colab install [-s NAME] [-r FILE | PKG...]` — Install packages on the VM using
`uv` (falls back to `pip`)"
This confirms package installation is a runtime-level operation, performed against the
VM, not a property of the notebook file itself.
## Corroborating evidence from google.colab.drive
In `googlecolab/colabtools`, `google/colab/drive.py` defines:
```python
def mount(mountpoint,
```

**[2] colab-filesystem-conventions** — Colab CLI README - runtime filesystem and drive mount  
<https://github.com/googlecolab/google-colab-cli>
```text
force_remount=False, timeout_ms=120000, readonly=False):
 """Mount your Google Drive at the specified mountpoint path."""
```
and the implementation raises `NotImplementedError` with "Mounting drive is unsupported
in this environment" unless `/var/colab/hostname` exists. This is direct evidence that
the `google.colab` package only functions inside an actual Colab VM, which is why
notebooks importing it carry a Colab-environment dependency.
## What this source does not establish
This source does not state that a specific path referenced by a notebook exists on any
given runtime version.
```

**[3] colab-filesystem-conventions** — Colab CLI README - runtime filesystem and drive mount  
<https://github.com/googlecolab/google-colab-cli>
```text
## Filesystem operations exist against a VM filesystem
Quoted command descriptions from the official README:
- "`colab upload [-s NAME] LOCAL REMOTE` — Upload a local file to the VM filesystem"
- "`colab download [-s NAME] REMOTE LOCAL` — Download a file from the VM filesystem"
- "`colab rm [-s NAME] PATH` — Remove a remote file from the VM filesystem"
- "`colab edit [-s NAME] PATH` — Edit a remote file in-place using your local `$EDITOR`"
## `/content/drive` is the default Drive mount path
Quoted: "`colab drivemount [-s NAME] [PATH]` — Mount Google Drive on the VM (default:
`/content/drive`)"
```

**[4] colab-backend-info-transparency** — Google Colab Adds More Back to School Improvements!  
<https://developers.googleblog.com/en/google-colab-adds-more-back-to-school-improvements/>
```text
## The challenge of a dynamic runtime
Quoted from the official Google Colab announcement:
"Colab Runtimes are continuously updated with the latest software packages, security
patches, and features. While this ensures you always have access to modern tools and
safe environments, it can lead to challenges when you need to reproduce a specific
result created on an older runtime. With ongoing updates, core dependencies might
change, breaking your code in subtle or significant ways."
And:
"If you've ever tried to re-run a notebook from a few months ago and been met with a
wall of dependency or
```

## How much RAM does a free Colab runtime give me?

*Why this question was chosen:* NOT answerable. No curated source states a RAM figure, so the assistant must refuse rather than guess.

- Status: `insufficient_evidence`
- Passages retrieved: 4
- Evidence coverage: **0.30** (threshold 0.50)

### Refused

The nearest passages in the curated corpus do not cover enough of the question to answer it (coverage 0.30, threshold 0.50). Showing them anyway, unverified.

The passages below are shown anyway so the refusal is inspectable, but no answer was generated and the model was not called at all.

### Retrieved passages

**[1] colab-backend-info-transparency** — Google Colab Adds More Back to School Improvements!  
<https://developers.googleblog.com/en/google-colab-adds-more-back-to-school-improvements/>
```text
## The challenge of a dynamic runtime
Quoted from the official Google Colab announcement:
"Colab Runtimes are continuously updated with the latest software packages, security
patches, and features. While this ensures you always have access to modern tools and
safe environments, it can lead to challenges when you need to reproduce a specific
result created on an older runtime. With ongoing updates, core dependencies might
change, breaking your code in subtle or significant ways."
And:
"If you've ever tried to re-run a notebook from a few months ago and been met with a
wall of dependency or
```

**[2] colab-runtime-version-faq** — Frequently Asked Questions - Past Runtime Versions  
<https://research.google.com/colaboratory/runtime-version-faq.html>
```text
## What is a Runtime Version?
Colab runtimes come with many libraries, packages, and binaries pre-installed. Colab
updates these frequently in order to provide users with new capabilities and bug fixes.
Runtime Versions refer to past versions of the Colab runtime.
## Why would I want to use a past runtime version?
Google generally recommends using the latest runtime version, which all notebooks are
configured to do by default, and adding code to a notebook to install specific versions
of libraries that are needed. However, some users may prefer to pin their runtime to a
past version. Stated
```

**[3] colab-runtime-version-faq** — Frequently Asked Questions - Past Runtime Versions  
<https://research.google.com/colaboratory/runtime-version-faq.html>
```text
reasons include:
- The notebook is used by a wide audience, such as in a class or workshop, and the
 author wants to ensure that Colab updates do not break the notebook.
- Colab updates a core dependency that cannot be changed back, such as the Python version.
## Caveats of pinning to a past runtime version
Quoted from the FAQ:
- "It can take 2-3 minutes to connect to a past runtime version, instead of the few
 seconds it takes to connect to a default runtime. This is because we need to download
 the past version image and restart the runtime."
- "Some newer Colab features that rely on newer
```

**[4] colab-pip-install-behaviour** — google.colab._pip - pip install post-install warning behaviour  
<https://github.com/googlecolab/colabtools/blob/main/google/colab/_pip.py>
```text
does not state that any particular notebook will fail. It describes Colab's own
handling of pip runs inside a runtime.
```

## How to read this report

- Every answer above is built only from the passages printed under it. The prompt contains the question and those passages and nothing else.
- Coverage is computed by deterministic code before the model is called. The third question never reaches the model.
- A citation to a source outside the retrieved set would be withheld from the reference list rather than rendered as a real link.
- Retrieval, embeddings and the vector database run locally. Only answer generation calls a provider.
