# PROJECT_SPEC.md

## PROJECT NAME

Colab Notebook Compatibility Auditor

## PROBLEM

Older Colab notebooks often contain explicit package versions, `pip install` commands, imports, and runtime assumptions (for example `/content/` paths). Colab runtimes are updated frequently, so those assumptions become risky as the runtime changes.

## USER

A data-science learner or developer trying to reuse an older Colab notebook.

## INPUT

- A `.ipynb` notebook file (uploaded, never executed)
- A selected Colab runtime snapshot (for example `2026.07`, `2025.07`)

## OUTPUT

A structured compatibility report with explicit status, deterministic findings, retrieved evidence, recommended manual checks, and limitations.

## REPORT STATES

| State | Meaning |
|---|---|
| `READY` | No obvious risk detected by the implemented checks. |
| `ATTENTION` | One or more detectable risks or assumptions worth reviewing. |
| `HIGH_RISK` | One or more deterministic high-severity rule violations. |
| `UNKNOWN` | Insufficient evidence to conclude; manual verification required. |

`READY` means: "No obvious risk detected by the implemented checks."

`READY` does **not** mean: "The notebook is guaranteed to run."

## DETECTABLE SIGNALS FOR MVP

1. `pip install` commands (including `%pip` and `!pip` forms)
2. Explicit package versions
3. Package / import names, including import-name to distribution-name mappings
4. Explicit version mismatch against the selected runtime snapshot
5. Obvious environment / package assumptions
6. Simple Colab-specific path indicators such as `/content/`
7. Unknown or unsupported cases

## OUT OF SCOPE

- Automatic execution
- Automatic repair
- Package solver
- Full static analysis
- Full dependency graph
- Arbitrary Jupyter environment support
- OS-level diagnosis
- Credentials debugging
- Network debugging
- Proof that arbitrary notebook code will execute

## NON-NEGOTIABLE SAFETY CLAIM

Static analysis cannot guarantee execution. Every report must state this.