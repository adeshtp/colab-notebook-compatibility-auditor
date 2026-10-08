"""Deterministic tests for knowledge ingestion and retrieval.

These build the real LanceDB index once per session. That is slower than the
Session 2 tests but still runs offline with no API key.
"""

import pytest

from knowledge_base import (
    EMBEDDING_MODEL,
    build_knowledge,
    ingest,
    load_sources,
    retrieve,
)


@pytest.fixture(scope="module")
def knowledge():
    kb = build_knowledge(rebuild=True)
    ingest(kb)
    return kb


def test_manifest_sources_all_exist_on_disk():
    sources = load_sources()

    assert len(sources) == 5
    assert all(source["path"].is_file() for source in sources)


def test_manifest_sources_are_all_official_and_marked_as_facts():
    for source in load_sources():
        assert source["content_type"] == "SOURCE_FACT"
        assert source["url"].startswith("https://")


def test_ingest_inserts_every_curated_source(knowledge):
    hits = retrieve(knowledge, "Colab runtime version pinning", max_results=5)
    indexed = {hit["source_id"] for hit in hits}

    assert indexed
    assert indexed <= {source["source_id"] for source in load_sources()}


def test_retrieval_preserves_source_metadata(knowledge):
    hits = retrieve(knowledge, "/content/drive filesystem path")

    assert hits
    assert all(hit["source_id"] for hit in hits)
    assert all(hit["url"].startswith("https://") for hit in hits)
    assert all(hit["content_type"] == "SOURCE_FACT" for hit in hits)


def test_retrieval_finds_the_filesystem_source_for_content_path_queries(knowledge):
    hits = retrieve(knowledge, "/content/drive filesystem path assumption")
    top = hits[0]["source_id"]

    assert top == "colab-filesystem-conventions"


def test_retrieval_finds_the_snapshot_caveat_for_absent_packages(knowledge):
    hits = retrieve(knowledge, "pip freeze list may not reflect the live runtime")
    top = hits[0]["source_id"]

    assert top == "colab-backend-info-readme"


def test_retrieval_respects_the_result_cap(knowledge):
    hits = retrieve(knowledge, "Colab runtime", max_results=2)

    assert len(hits) <= 2


def test_embedding_model_is_local_and_free():
    assert EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"