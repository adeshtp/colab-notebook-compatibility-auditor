"""The deterministic compatibility rules, R001 to R006.

Each function takes plain data and returns Finding objects. No LLM, no network.
"""

from collections import defaultdict

import notebook_parser
import runtime_checker
from models import AuditResult, Finding, Requirement


def check_version_mismatch(
    dependencies: list[Requirement], packages: dict[str, str]
) -> list[Finding]:
    """R001: notebook pins a version that differs from the selected runtime."""
    findings = []

    for dependency in dependencies:
        if not dependency.version:
            continue
        runtime_version = runtime_checker.version_in_snapshot(packages, dependency.name)
        if not runtime_version:
            continue
        if runtime_checker.versions_match(dependency.version, runtime_version):
            continue

        findings.append(
            Finding(
                rule="R001",
                package=dependency.name,
                severity="HIGH",
                status="RISK",
                cell=dependency.cell,
                message=(
                    f"Notebook pins {dependency.name}=={dependency.version} but the "
                    f"selected runtime contains {runtime_version}."
                ),
            )
        )

    return findings


def check_unpinned(dependencies: list[Requirement]) -> list[Finding]:
    """R002: a package the notebook installs has no exact version pin.

    Only pip installs are reported. Reporting every bare import as unpinned would
    bury the real signal under noise.
    """
    findings = []

    for dependency in dependencies:
        if dependency.origin != "pip_install" or dependency.version:
            continue

        findings.append(
            Finding(
                rule="R002",
                package=dependency.name,
                severity="ATTENTION",
                status="RISK",
                cell=dependency.cell,
                message=(
                    f"Notebook installs {dependency.name} with no exact version pin "
                    f"({dependency.raw}). The runtime version it resolves to is not "
                    f"guaranteed to be stable."
                ),
            )
        )

    return findings


def check_conflicting_installs(dependencies: list[Requirement]) -> list[Finding]:
    """R005: the notebook asks for more than one version of the same package."""
    by_package: dict[str, list[Requirement]] = defaultdict(list)
    for dependency in dependencies:
        if dependency.origin == "pip_install":
            by_package[dependency.name].append(dependency)

    findings = []
    for name, group in by_package.items():
        constraints = {item.version or "no pin" for item in group}
        if len(constraints) < 2:
            continue

        requested = ", ".join(item.raw for item in group)
        findings.append(
            Finding(
                rule="R005",
                package=name,
                severity="HIGH",
                status="RISK",
                cell=group[0].cell,
                message=(
                    f"Notebook requests {name} more than once with different "
                    f"requirements ({requested}). The effective version depends on "
                    f"execution order."
                ),
            )
        )

    return findings


def check_absent_from_runtime(
    dependencies: list[Requirement], packages: dict[str, str]
) -> list[Finding]:
    """R004: a package is not listed in the selected runtime snapshot.

    This is reported as UNKNOWN. Snapshot data can lag a live runtime, so absence
    is not proof that an import will fail.
    """
    findings = []

    for dependency in dependencies:
        if runtime_checker.version_in_snapshot(packages, dependency.name):
            continue

        findings.append(
            Finding(
                rule="R004",
                package=dependency.name,
                severity="UNKNOWN",
                status="UNKNOWN",
                cell=dependency.cell,
                message=(
                    f"{dependency.name} is not listed in the selected runtime "
                    f"snapshot. Installing it at runtime may be required. Verify "
                    f"manually; snapshot data can lag a live runtime."
                ),
            )
        )

    return findings


def check_content_paths(paths: list[tuple[int, str]]) -> list[Finding]:
    """R003: the notebook references Colab's /content/ filesystem."""
    if not paths:
        return []

    cells = sorted({cell for cell, _ in paths})
    examples = ", ".join(sorted({path for _, path in paths})[:3])

    return [
        Finding(
            rule="R003",
            severity="ATTENTION",
            status="RISK",
            cell=cells[0],
            message=(
                f"Notebook references {len(paths)} Colab /content/ path(s) in cells "
                f"{cells}, for example '{examples}'. This is a Colab environment "
                f"assumption, not an error; the paths must exist on the runtime."
            ),
        )
    ]


def aggregate_status(findings: list[Finding]) -> str:
    """Worst finding decides the status."""
    severities = {finding.severity for finding in findings}

    if "HIGH" in severities:
        return "HIGH_RISK"
    if "ATTENTION" in severities:
        return "ATTENTION"
    if "UNKNOWN" in severities:
        return "UNKNOWN"
    return "READY"


def audit_notebook(notebook_path: str, snapshot: str | None) -> AuditResult:
    """Parse a notebook, compare it against a runtime snapshot, return findings."""
    name = notebook_path.rsplit("/", 1)[-1]

    try:
        dependencies = notebook_parser.extract_dependencies(notebook_path)
        content_paths = notebook_parser.find_content_paths(notebook_path)
    except ValueError as exc:
        return AuditResult(
            notebook_name=name,
            findings=[
                Finding(
                    rule="R006",
                    severity="UNKNOWN",
                    status="UNKNOWN",
                    message=f"Notebook could not be parsed, so no conclusion is possible: {exc}",
                )
            ],
            status="UNKNOWN",
        )

    findings: list[Finding] = []

    if not snapshot:
        findings.append(
            Finding(
                rule="R006",
                severity="UNKNOWN",
                status="UNKNOWN",
                message=(
                    "No runtime snapshot was selected, so version compatibility "
                    "cannot be checked. Select a snapshot to enable R001 and R004."
                ),
            )
        )
        return AuditResult(
            notebook_name=name,
            dependencies=dependencies,
            findings=findings + check_content_paths(content_paths),
            status="UNKNOWN",
        )

    packages, runtime = runtime_checker.load_snapshot(snapshot)

    findings += check_conflicting_installs(dependencies)
    findings += check_version_mismatch(dependencies, packages)
    findings += check_unpinned(dependencies)
    findings += check_absent_from_runtime(dependencies, packages)
    findings += check_content_paths(content_paths)

    return AuditResult(
        notebook_name=name,
        runtime=runtime,
        dependencies=dependencies,
        findings=findings,
        status=aggregate_status(findings),
    )