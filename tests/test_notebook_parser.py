import notebook_parser
import pytest

FIXTURES = "tests/fixtures"


def fixture(name: str) -> str:
    return f"{FIXTURES}/{name}.ipynb"


def test_extracts_pinned_and_bare_installs():
    found = notebook_parser.extract_dependencies(fixture("mismatching_pin"))

    assert [(item.name, item.version) for item in found] == [("numpy", "1.24.3"), ("pandas", "2.2.2")]


def test_extracts_imports_not_already_installed():
    names = [item.name for item in notebook_parser.extract_dependencies(fixture("clean_notebook"))]

    assert names == ["pandas", "numpy"]


def test_standard_library_and_first_party_imports_are_ignored():
    names = [item.name for item in notebook_parser.extract_dependencies(fixture("clean_notebook"))]

    assert "os" not in names
    assert "warnings" not in names


def test_package_names_in_prose_do_not_count_as_dependencies():
    names = [item.name for item in notebook_parser.extract_dependencies(fixture("clean_notebook"))]

    assert "gensim" not in names
    assert "opendatasets" not in names


def test_percent_pip_magic_is_recognised():
    found = notebook_parser.extract_dependencies(fixture("unknown_package"))

    assert found[0].name == "some-nonexistent-package-xyz"
    assert found[0].version == "9.9.9"
    assert found[0].origin == "pip_install"


def test_bare_pip_install_without_a_magic_prefix_is_recognised():
    found = notebook_parser.parse_install_commands("pip install nltk")

    assert found == ["nltk"]


def test_flag_arguments_are_not_treated_as_packages():
    assert notebook_parser.split_requirements("-q --upgrade nltk sentence-transformers") == [
        "nltk",
        "sentence-transformers",
    ]


def test_quoted_requirement_names_are_handled():
    assert notebook_parser.split_requirements('"agno[pdf]" lancedb') == ["agno[pdf]", "lancedb"]


def test_unparseable_install_lines_are_skipped():
    assert notebook_parser.extract_dependencies(fixture("malformed_install")) == []


def test_content_paths_are_found_with_cell_index():
    assert notebook_parser.find_content_paths(fixture("content_paths")) == [
        (0, "/content/fraud-detection/fraudTrain.csv")
    ]


def test_import_name_maps_to_distribution_name():
    assert notebook_parser.resolve_import("sklearn.ensemble") == "scikit-learn"
    assert notebook_parser.resolve_import("cv2") == "opencv-python"


def test_only_a_literal_version_counts_as_an_exact_pin():
    assert notebook_parser.parse_requirement("numpy==1.24.3", 0, "pip_install").version == "1.24.3"
    assert notebook_parser.parse_requirement("scikit-learn>=1.0", 0, "pip_install").version is None
    assert notebook_parser.parse_requirement("numpy==1.24.*", 0, "pip_install") is None
    assert notebook_parser.parse_requirement("pkg==1.0.0,!=1.0.1", 0, "pip_install") is None
    assert notebook_parser.parse_requirement("tf==2.9.0 ; python<'3.11'", 0, "pip_install") is None


def test_name_normalisation():
    assert notebook_parser.normalise_name("Sentence_Transformers") == "sentence-transformers"
    assert notebook_parser.normalise_name("bs4") == "bs4"


def test_non_notebook_file_is_rejected():
    with pytest.raises(ValueError):
        notebook_parser.read_notebook("README.md")