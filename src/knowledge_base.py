"""Local RAG over the curated Colab sources in data/sources/.

Same mechanism as the Agno reference notebook (Knowledge + LanceDb +
SentenceTransformerEmbedder), using the Agno 3.x API. Everything runs locally:
no API key, no cloud database.
"""

import json
import shutil
from pathlib import Path

from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.markdown_reader import MarkdownReader
from agno.vectordb.lancedb import LanceDb, SearchType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = PROJECT_ROOT / "data" / "sources"
DB_DIR = PROJECT_ROOT / "data" / "lancedb"
MANIFEST = SOURCES_DIR / "manifest.json"
TABLE_NAME = "colab_sources"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# How many chunks to return per search. Deliberately small: this is targeted
# evidence lookup, not an open-ended question-answering index.
DEFAULT_MAX_RESULTS = 3

# Sources are 2-3 KB each, so they land as one chunk by default. Splitting on
# headings means a retrieved chunk is the relevant section rather than the whole
# document, and the front matter lands in its own chunk instead of crowding out
# the body text.
CHUNK_SIZE = 600


def build_knowledge(db_dir: Path | str = DB_DIR, rebuild: bool = False) -> Knowledge:
    """Create the Knowledge object backed by a local LanceDB directory."""
    db_dir = Path(db_dir)

    # A half-finished ingest from an interrupted run would poison later searches,
    # so start clean when asked or when the directory looks unusable.
    if rebuild and db_dir.exists():
        shutil.rmtree(db_dir)

    vector_db = LanceDb(
        table_name=TABLE_NAME,
        uri=str(db_dir),
        search_type=SearchType.vector,
        embedder=SentenceTransformerEmbedder(id=EMBEDDING_MODEL),
    )

    return Knowledge(vector_db=vector_db)


def load_sources(sources_dir: Path | str = SOURCES_DIR) -> list[dict]:
    """Read the curated source manifest, keeping only files that exist."""
    manifest = json.loads(Path(MANIFEST).read_text(encoding="utf-8"))

    sources = []
    for entry in manifest["sources"]:
        path = Path(sources_dir) / entry["file"]
        if path.is_file():
            sources.append({**entry, "path": path})

    return sources


def ingest(knowledge: Knowledge, sources_dir: Path | str = SOURCES_DIR) -> list[str]:
    """Insert every curated source file into the vector store.

    Returns the file names that were ingested. Rebuild is the caller's choice so
    that repeated demo runs do not re-embed the corpus.
    """
    inserted = []

    for source in load_sources(sources_dir):
        knowledge.insert(
            name=source["source_id"],
            description=source["title"],
            path=str(source["path"]),
            reader=MarkdownReader(chunk_size=CHUNK_SIZE),
            metadata={
                "source": source["source"],
                "title": source["title"],
                "url": source["url"],
                "runtime_context": source["runtime_context"],
                "content_type": source["content_type"],
            },
            skip_if_exists=True,
        )
        inserted.append(source["file"])

    return inserted


def retrieve(knowledge: Knowledge, query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    """Search the curated sources and return plain inspectable dicts.

    No LLM decides whether or what to search. The query is built by the caller
    from deterministic facts. Results come back in similarity order; Agno 3.1.1
    does not expose the raw score on the returned Document, so rank is recorded
    instead of a fabricated number.
    """
    results = []

    for rank, document in enumerate(knowledge.search(query=query, max_results=max_results), start=1):
        metadata = document.meta_data or {}
        results.append(
            {
                "source_id": document.name or "",
                "source": metadata.get("source", ""),
                "title": metadata.get("title", ""),
                "url": metadata.get("url", ""),
                "content_type": metadata.get("content_type", ""),
                "runtime_context": metadata.get("runtime_context", ""),
                "content": (document.content or "")[:600],
                "rank": rank,
            }
        )

    return results