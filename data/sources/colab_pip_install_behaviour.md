---
source_id: colab-pip-install-behaviour
source: googlecolab/colabtools
title: "google.colab._pip - pip install post-install warning behaviour"
url: https://github.com/googlecolab/colabtools/blob/main/google/colab/_pip.py
retrieved: 2026-10-08
runtime_context: all
content_type: SOURCE_FACT
---

## A pip install can invalidate already-imported modules

`google/colab/_pip.py` in the official `googlecolab/colabtools` repository contains
`_previously_imported_packages` and `print_previous_import_warning`. The function
computes which top-level packages were installed by a pip run and are already present
in `sys.modules`, then emits a warning that the Colab frontend displays with a restart
button:

```python
def _previously_imported_packages(pip_output):
  """List all previously imported packages from a pip install."""
  installed = set(_extract_toplevel_packages(pip_output))
  return sorted(installed.intersection(set(sys.modules)))

def print_previous_import_warning(output):
  if packages:
    # display a warning + restart button by the Colab frontend
```

## Why this matters for compatibility auditing

This is official evidence for a deterministic, checkable signal: a notebook that
installs a package **after** importing it in an earlier cell can end up with the
previously imported version still bound in memory. The recommended resolution is a
runtime restart.

This is a state-ordering risk that cannot be resolved by comparing version strings
alone, which is why the auditor reports install cell ordering rather than silently
assuming the last `pip install` wins.

## Distribution-to-module resolution is not identity

The same file builds a reverse map using `importlib.metadata.packages_distributions()`,
which maps an import module name to the distributions that provide it. This confirms
that import name and distribution name are distinct concepts and that a naive
name comparison is wrong for packages such as `sklearn` (provided by `scikit-learn`),
`cv2` (provided by `opencv-python`), and `bs4` (provided by `beautifulsoup4`).

## What this source does not establish

It does not state that any particular notebook will fail. It describes Colab's own
handling of pip runs inside a runtime.