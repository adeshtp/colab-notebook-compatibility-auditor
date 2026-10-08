import rules

FIXTURES = "tests/fixtures"
SNAPSHOT = "2026.07"


def audit(name: str, snapshot: str | None = SNAPSHOT):
    return rules.audit_notebook(f"{FIXTURES}/{name}.ipynb", snapshot)


def rules_fired(result) -> list[str]:
    return [finding.rule for finding in result.findings]


def test_matching_pin_produces_no_mismatch():
    result = audit("matching_pin")

    assert "R001" not in rules_fired(result)
    assert result.status == "READY"


def test_mismatching_pin_is_high_risk():
    result = audit("mismatching_pin")
    mismatch = [f for f in result.findings if f.rule == "R001"]

    assert result.status == "HIGH_RISK"
    assert len(mismatch) == 1
    assert mismatch[0].package == "numpy"
    assert "1.24.3" in mismatch[0].message
    assert "2.0.2" in mismatch[0].message


def test_unpinned_install_is_attention_not_incompatibility():
    result = audit("unpinned_package")
    unpinned = [f for f in result.findings if f.rule == "R002"]

    assert len(unpinned) == 1
    assert unpinned[0].package == "opendatasets"
    assert unpinned[0].severity == "ATTENTION"
    assert "no exact version pin" in unpinned[0].message


def test_package_absent_from_runtime_is_unknown():
    result = audit("unknown_package")
    absent = [f for f in result.findings if f.rule == "R004"]

    assert len(absent) == 1
    assert absent[0].package == "some-nonexistent-package-xyz"
    assert absent[0].severity == "UNKNOWN"
    assert absent[0].status == "UNKNOWN"
    assert "may be required" in absent[0].message


def test_status_aggregation_order():
    def finding(severity):
        return rules.Finding(rule="R00X", severity=severity, status="RISK", message="")

    assert rules.aggregate_status([]) == "READY"
    assert rules.aggregate_status([finding("INFO")]) == "READY"
    assert rules.aggregate_status([finding("UNKNOWN")]) == "UNKNOWN"
    assert rules.aggregate_status([finding("UNKNOWN"), finding("ATTENTION")]) == "ATTENTION"
    assert rules.aggregate_status([finding("ATTENTION"), finding("HIGH")]) == "HIGH_RISK"


def test_conflicting_installs_are_high_risk():
    result = audit("conflicting_install")
    conflict = [f for f in result.findings if f.rule == "R005"]

    assert result.status == "HIGH_RISK"
    assert conflict[0].package == "numpy"
    assert "numpy==2.0.2" in conflict[0].message
    assert "numpy==1.24.3" in conflict[0].message


def test_content_path_is_reported_as_an_assumption():
    result = audit("content_paths")

    assert "R003" in rules_fired(result)
    assert result.status == "ATTENTION"
    assert "/content/" in result.findings[0].message


def test_clean_notebook_is_ready():
    result = audit("clean_notebook")

    assert result.status == "READY"
    assert result.findings == []


def test_missing_snapshot_returns_unknown_instead_of_guessing():
    result = audit("mismatching_pin", snapshot=None)

    assert result.status == "UNKNOWN"
    assert rules_fired(result) == ["R006"]
    assert result.dependencies


def test_missing_file_returns_unknown_rather_than_raising():
    result = rules.audit_notebook("tests/fixtures/does_not_exist.ipynb", SNAPSHOT)

    assert result.status == "UNKNOWN"
    assert rules_fired(result) == ["R006"]


def test_unparseable_notebook_returns_unknown_rather_than_raising():
    result = rules.audit_notebook("README.md", SNAPSHOT)

    assert result.status == "UNKNOWN"
    assert rules_fired(result) == ["R006"]


def test_report_serialises_to_json():
    result = audit("mismatching_pin")

    assert '"rule": "R001"' in result.model_dump_json(indent=2)