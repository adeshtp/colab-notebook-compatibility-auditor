import runtime_checker


def test_snapshots_are_available_locally():
    snapshots = runtime_checker.list_snapshots()

    assert "2026.07" in snapshots
    assert "2025.07" in snapshots


def test_package_versions_load_from_a_snapshot():
    packages, info = runtime_checker.load_snapshot("2026.07")

    assert packages["numpy"] == "2.0.2"
    assert packages["scikit-learn"] == "1.6.1"
    assert info.python_version == "3.12.13"
    assert info.os_version == "Ubuntu 22.04.5 LTS"
    assert info.source_commit


def test_older_snapshot_has_a_different_python_version():
    _, info = runtime_checker.load_snapshot("2025.07")

    assert info.python_version == "3.11.13"


def test_direct_reference_lines_are_parsed():
    packages, _ = runtime_checker.load_snapshot("2026.07")

    assert packages["torch"] == "2.11.0"


def test_git_reference_lines_are_skipped_because_they_carry_no_version():
    parsed = runtime_checker.parse_freeze(
        "jupyter_kernel_gateway @ git+https://github.com/googlecolab/kernel_gateway@abc123"
    )

    assert parsed == {}


def test_absence_from_the_index_returns_none():
    packages, _ = runtime_checker.load_snapshot("2026.07")

    assert runtime_checker.version_in_snapshot(packages, "opendatasets") is None
    assert runtime_checker.version_in_snapshot(packages, "OpenDataSets") is None


def test_local_build_tags_are_ignored_when_comparing():
    assert runtime_checker.versions_match("2.11.0", "2.11.0+cpu")
    assert not runtime_checker.versions_match("2.10.0", "2.11.0")


def test_unknown_snapshot_is_rejected():
    try:
        runtime_checker.load_snapshot("1999.01")
    except ValueError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("expected ValueError")