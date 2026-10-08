"""Plain data shapes returned by the deterministic audit.

No logic here beyond field definitions and validation.
"""

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    """One package reference found in a notebook cell."""

    name: str = Field(description="Normalised distribution name, e.g. scikit-learn")
    version: str | None = Field(default=None, description="Exact == pin, else None")
    raw: str = Field(description="Text as written in the notebook, specifier included")
    cell: int = Field(description="Zero-based notebook cell index")
    origin: str = Field(description="'pip_install' or 'import'")


class Finding(BaseModel):
    """One deterministic rule result. Never model-generated."""

    rule: str = Field(description="Rule id, e.g. R001")
    package: str | None = None
    severity: str = Field(description="HIGH, ATTENTION, INFO or UNKNOWN")
    status: str = Field(description="RISK, INFO or UNKNOWN")
    message: str
    cell: int | None = None


class RuntimeInfo(BaseModel):
    """The runtime snapshot the notebook was compared against."""

    snapshot: str
    source_commit: str | None = None
    python_version: str | None = None
    os_version: str | None = None


class AuditResult(BaseModel):
    """Everything the deterministic stage produces."""

    notebook_name: str
    runtime: RuntimeInfo | None = None
    dependencies: list[Requirement] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    status: str = Field(description="READY, ATTENTION, HIGH_RISK or UNKNOWN")