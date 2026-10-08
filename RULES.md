# RULES.md — Deterministic Compatibility Rules

Each rule is testable and implemented as pure Python. Rules never call an LLM and never perform network access.

Severity vocabulary:

- `HIGH` — a concrete, checkable conflict. Report as `HIGH_RISK` contributor.
- `ATTENTION` — a real signal that needs human review. Not an error.
- `INFO` — a recorded observation with no compatibility judgement.
- `UNKNOWN` — evidence is insufficient. Report `UNKNOWN`, do not guess.

---

## R001 — Explicit Package Version Mismatch

**Definition**
The notebook explicitly pins distribution `P` to version `Vn`, and the selected runtime snapshot reports `P` at version `Vr`, where `Vn != Vr`.

**Detection logic**
1. Parse each `pip install` requirement for `P`.
2. Normalise `P` to a distribution name.
3. Look up `Vr` in the runtime snapshot package index.
4. Compare using `==` equality semantics only. Compatible-range specifiers (`>=`, `<`, `~=`) are handled by R002, not R001.

**Severity** `HIGH`

**Expected behaviour**
Emit finding `R001` with `package`, `notebook_version`, `runtime_version`, and the notebook cell index as evidence.

**Limitation**
A mismatch does not prove runtime failure. Colab runtimes may still resolve the pinned version, and the notebook may not import the affected package at all.

---

## R002 — Unpinned Package / Non-Exact Requirement

**Definition**
The notebook references a package but provides no exact `==` pin, or provides only a range or bare name.

**Detection logic**
A package referenced by `pip install` or by a third-party `import` has no exact pin.

**Severity** `ATTENTION`

**Expected behaviour**
Report "No explicit version pin found." Do not claim incompatibility. Range specifiers (`>=1.0`) are recorded verbatim in `detected_dependencies`.

**Limitation**
An unpinned package is normal notebook practice, not a defect.

---

## R003 — Colab Path Assumption

**Definition**
The notebook contains explicit `/content/` filesystem references.

**Detection logic**
Scan cell source for the literal `/content/` prefix.

**Severity** `ATTENTION`

**Expected behaviour**
Report as an environment assumption, not an error, with the matched paths and cell indices.

**Limitation**
`/content/` is the standard Colab working directory. Detection confirms the assumption exists; it does not confirm the referenced path exists in the snapshot.

---

## R004 — Package Absent From Runtime Metadata

**Definition**
A distribution detected in the notebook is not present in the selected runtime snapshot's package index.

**Detection logic**
Normalise the package name, then check membership in the snapshot index. Standard-library and first-party modules are excluded via a fixed local module list.

**Severity** `UNKNOWN`

**Expected behaviour**
Report as `UNKNOWN`, requiring manual verification. State that installation at runtime may be required. Do **not** state that installation will fail.

**Limitation**
Snapshot package lists are published from CI submissions and may lag the live runtime. Absence in metadata is not proof of absence in a running runtime.

---

## R005 — Conflicting Package Installation

**Definition**
The notebook explicitly requests more than one distinct version constraint for the same distribution.

**Detection logic**
Group parsed requirements by normalised distribution name. A group is conflicting when two requirements pin different exact versions, or when one pins an exact version while another requests a different version.

**Severity** `HIGH`

**Expected behaviour**
Report all requirements in the conflicting group, with cell indices, and state that the effective version depends on execution order.

**Limitation**
The auditor does not resolve the conflict and does not run a solver. Cell order is recorded but the auditor does not simulate pip behaviour.

---

## R006 — Insufficient Evidence

**Definition**
No reliable rule or authoritative source establishes a compatibility conclusion.

**Detection logic**
Applies when: the notebook cannot be parsed; no runtime snapshot is selected; or a detected package cannot be resolved to a distribution name through the known mapping and import heuristics.

**Severity** `UNKNOWN`

**Expected behaviour**
Return `UNKNOWN`. Report what was detected and what is missing. Never fill the gap with model output.

**Limitation**
`UNKNOWN` is a correct result, not a failure of the tool.

---

## R007 — Malformed Install Command

**Definition**
A cell contains a `pip install` invocation that the parser cannot interpret into requirements.

**Detection logic**
The install command is recognised but yields zero parseable requirements, for example an unsupported shell construct or an unparseable version specifier.

**Severity** `ATTENTION`

**Expected behaviour**
Report the raw command text as unparsed. Do not guess the intended requirement. Feed R006 when nothing about the notebook can be concluded.

**Limitation**
The parser reads text only. It cannot evaluate shell expansion or conditionals.

---

## Status aggregation

- Any `HIGH` finding → `HIGH_RISK`
- Otherwise any `ATTENTION` finding → `ATTENTION`
- Otherwise any `UNKNOWN` finding, or an unresolvable input → `UNKNOWN`
- Otherwise → `READY`, meaning "no obvious risk detected by the implemented checks"

`READY` is never a guarantee of successful execution.