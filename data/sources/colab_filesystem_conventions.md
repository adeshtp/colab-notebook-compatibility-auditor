---
source_id: colab-filesystem-conventions
source: googlecolab/google-colab-cli (official Google Colab organisation)
title: "Colab CLI README - runtime filesystem and drive mount"
url: https://github.com/googlecolab/google-colab-cli
retrieved: 2026-10-08
runtime_context: all
content_type: SOURCE_FACT
---

## Filesystem operations exist against a VM filesystem

Quoted command descriptions from the official README:

- "`colab upload [-s NAME] LOCAL REMOTE` — Upload a local file to the VM filesystem"
- "`colab download [-s NAME] REMOTE LOCAL` — Download a file from the VM filesystem"
- "`colab rm [-s NAME] PATH` — Remove a remote file from the VM filesystem"
- "`colab edit [-s NAME] PATH` — Edit a remote file in-place using your local `$EDITOR`"

## `/content/drive` is the default Drive mount path

Quoted: "`colab drivemount [-s NAME] [PATH]` — Mount Google Drive on the VM (default:
`/content/drive`)"

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
def mount(mountpoint, force_remount=False, timeout_ms=120000, readonly=False):
  """Mount your Google Drive at the specified mountpoint path."""
```

and the implementation raises `NotImplementedError` with "Mounting drive is unsupported
in this environment" unless `/var/colab/hostname` exists. This is direct evidence that
the `google.colab` package only functions inside an actual Colab VM, which is why
notebooks importing it carry a Colab-environment dependency.

## What this source does not establish

This source does not state that a specific path referenced by a notebook exists on any
given runtime version. Detection of `/content/` references confirms an environment
assumption, not a satisfied requirement.