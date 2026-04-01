"""Document indexer: loads, chunks, and indexes documents into vector store.

Usage:
    python -m pave_agent.rag.indexer --input-dir ./docs
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from pave_lib.db import vector_store

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by character count.

    Uses paragraph boundaries when possible, falls back to character splitting.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current.strip())
            # Keep overlap from end of previous chunk
            current = current[-overlap:] if len(current) > overlap else current
        current += "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def index_file(file_path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> int:
    """Index a single text file into the vector store.

    Returns number of chunks indexed.
    """
    text = file_path.read_text(encoding="utf-8")
    chunks = chunk_text(text, chunk_size)

    if not chunks:
        return 0

    source = file_path.name
    ids = [f"{source}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source, "chunk_index": i} for i in range(len(chunks))]

    vector_store.add_documents(documents=chunks, metadatas=metadatas, ids=ids)
    logger.info("Indexed %d chunks from %s", len(chunks), source)
    return len(chunks)


def index_directory(dir_path: Path, extensions: tuple[str, ...] = (".txt", ".md")) -> int:
    """Index all matching files in a directory.

    Returns total number of chunks indexed.
    """
    total = 0
    for ext in extensions:
        for file_path in sorted(dir_path.rglob(f"*{ext}")):
            total += index_file(file_path)
    logger.info("Total indexed: %d chunks from %s", total, dir_path)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Index documents into vector store")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing documents")
    parser.add_argument("--extensions", nargs="+", default=[".txt", ".md"], help="File extensions to index")
    args = parser.parse_args()

    index_directory(args.input_dir, tuple(args.extensions))
