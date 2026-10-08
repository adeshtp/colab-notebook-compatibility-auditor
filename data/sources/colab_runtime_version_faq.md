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

Google generally recommends using the latest runtime version, which all notebooks are
configured to do by default, and adding code to a notebook to install specific versions
of libraries that are needed. However, some users may prefer to pin their runtime to a
past version. Stated reasons include:

- The notebook is used by a wide audience, such as in a class or workshop, and the
  author wants to ensure that Colab updates do not break the notebook.
- Colab updates a core dependency that cannot be changed back, such as the Python version.

## Caveats of pinning to a past runtime version

Quoted from the FAQ:

- "It can take 2-3 minutes to connect to a past runtime version, instead of the few
  seconds it takes to connect to a default runtime. This is because we need to download
  the past version image and restart the runtime."
- "Some newer Colab features that rely on newer changes to the runtime may not work with
  past runtime versions."

## How do I use a past runtime version?

Quoted: "You can use a past runtime version by selecting it from the Runtime -> Change
runtime type dialog, with the 'Runtime Version' dropdown."

## How long does a past runtime version stay available?

Quoted: "Currently, past runtime versions are available for 1 year after their release."

## Published runtime versions and their headline components

As listed on the page when retrieved on 2026-10-08. Treat these as a summary; the exact
package set is authoritative only in `googlecolab/backend-info`.

### 2026.07
Ubuntu 22.04.5 LTS; Python 3.12.13; numpy 2.0.2; PyTorch 2.11.0; Jax 0.7.2;
TensorFlow 2.20.0 (not included in TPU runtimes); R 4.6.0; julia 1.12.6

### 2026.04
Ubuntu 22.04.5 LTS; Python 3.12.13; numpy 2.0.2; PyTorch 2.10.0; Jax 0.7.2;
TensorFlow 2.19.0 (not included in TPU runtimes); R 4.5.3; julia 1.11.5

### 2026.01
Ubuntu 22.04.5 LTS; Python 3.12.12; numpy 2.0.2; PyTorch 2.9.0; Jax 0.7.2;
TensorFlow 2.19.0 (not included in TPU runtimes); R 4.5.2; julia 1.11.5

### 2025.10
Ubuntu 22.04.4 LTS; Python 3.12.12; numpy 2.0.2; PyTorch 2.8.0; Jax 0.5.3;
TensorFlow 2.19.0 (not included in TPU runtimes); R 4.5.1; julia 1.11.5

### 2025.07
Ubuntu 22.04.04 LTS; Python 3.11.13; numpy 2.0.2; PyTorch 2.6.0; Jax 0.5.2;
TensorFlow 2.18.0 (not included in TPU runtimes); R 4.5.1; julia 1.10.9