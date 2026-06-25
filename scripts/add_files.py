"""
scripts/add_files.py
--------------------
Incrementally add NEW files to an existing ChromaDB vectorstore.
Already-embedded files are skipped automatically — no re-embedding needed.

Usage (from project root):
    # Add one specific file
    python scripts/add_files.py data/MyNewSOP.txt

    # Add multiple files
    python scripts/add_files.py data/NewSOP.txt "data/ALL-data-2026-06-24 19_21_40.csv"

    # Scan /data and add anything not yet embedded
    python scripts/add_files.py --scan
"""

import os
import sys
import csv
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()

# ── API Key Rotation ───────────────────────────────────────────────────────────
_api_keys = [k for k in [
    os.getenv("GOOGLE_API_KEY"),
    os.getenv("GOOGLE_API_KEY_2"),
] if k]

if not _api_keys:
    raise RuntimeError("No GOOGLE_API_KEY found in .env")

print(f"[init] Loaded {len(_api_keys)} API key(s) for rotation.")

def is_rate_limit_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(kw in msg for kw in ("429", "quota", "rate limit", "resource exhausted", "ratelimitexceeded"))

def get_embeddings(key_index: int) -> GoogleGenerativeAIEmbeddings:
    key = _api_keys[key_index % len(_api_keys)]
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=key,
    )

# ── Config ─────────────────────────────────────────────────────────────────────
DATA_DIR      = "./data"
DB_DIR        = "./db"
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 75
BATCH_SIZE    = 50
BATCH_DELAY   = 65

# ── Helpers ────────────────────────────────────────────────────────────────────
def get_indexed_sources(vectorstore: Chroma) -> set[str]:
    """Return the set of source filenames already in the vectorstore."""
    try:
        result = vectorstore.get(include=["metadatas"])
        return {
            os.path.basename(m["source"])
            for m in result["metadatas"]
            if m and "source" in m
        }
    except Exception:
        return set()


def load_txt(path: str) -> list[Document]:
    loader = TextLoader(path, encoding="utf-8")
    return loader.load()


def load_csv(path: str) -> list[Document]:
    docs = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if not any(v.strip() for v in row.values() if v):
                continue
            lines = [f"{col}: {val}" for col, val in row.items() if val and val.strip()]
            doc = Document(
                page_content="\n".join(lines),
                metadata={
                    "source": os.path.basename(path),
                    "row": i + 2,
                    "sales_order": row.get("Sales Order Number", "").strip(),
                    "customer": row.get("Customer Company", "").strip(),
                    "end_customer": row.get("End Customer Company", "").strip(),
                    "country": row.get("End Customer Installation Country", "").strip(),
                    "service_type": row.get("Service Type", "").strip(),
                },
            )
            docs.append(doc)
    return docs


def embed_chunks(vectorstore: Chroma, doc_chunks: list[Document]) -> None:
    """Embed chunks into the vectorstore with rate-limit-aware key rotation."""
    key_index = 0
    for i in range(0, len(doc_chunks), BATCH_SIZE):
        batch         = doc_chunks[i:i + BATCH_SIZE]
        batch_num     = (i // BATCH_SIZE) + 1
        total_batches = (len(doc_chunks) + BATCH_SIZE - 1) // BATCH_SIZE
        current_key   = (key_index % len(_api_keys)) + 1
        print(f"    Batch {batch_num}/{total_batches} ({len(batch)} chunks) [key #{current_key}]...")

        for attempt in range(3):
            try:
                emb = get_embeddings(key_index)
                vectorstore._embedding_function = emb  # swap key without recreating store
                vectorstore.add_documents(batch)
                break
            except Exception as e:
                if is_rate_limit_error(e):
                    if len(_api_keys) > 1:
                        key_index += 1
                        current_key = (key_index % len(_api_keys)) + 1
                        print(f"    [!] Rate limit - rotating to key #{current_key}.")
                    else:
                        print(f"    [!] Rate limit (no other key). Waiting 65s...")
                        time.sleep(65)
                else:
                    if attempt < 2:
                        wait = 30 * (attempt + 1)
                        print(f"    [!] Error attempt {attempt+1}: {e}. Retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"    [!] Failed after 3 attempts. Skipping batch.")
                        break

        if i + BATCH_SIZE < len(doc_chunks):
            print(f"    Waiting {BATCH_DELAY}s...")
            time.sleep(BATCH_DELAY)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Incrementally add files to ChromaDB.")
    parser.add_argument(
        "files", nargs="*",
        help="Path(s) to specific .txt or .csv file(s) to embed."
    )
    parser.add_argument(
        "--scan", action="store_true",
        help="Scan /data and embed any files not yet in the vectorstore."
    )
    args = parser.parse_args()

    if not args.files and not args.scan:
        parser.print_help()
        sys.exit(1)

    # ── Open (or create) the existing vectorstore ──────────────────────────────
    if not os.path.exists(DB_DIR):
        print(f"[!] No vectorstore found at '{DB_DIR}'.")
        print("    Run 'python scripts/create_index.py' first to build the initial index.")
        sys.exit(1)

    print(f"[1] Opening existing vectorstore at '{DB_DIR}'...")
    vectorstore = Chroma(
        persist_directory=DB_DIR,
        embedding_function=get_embeddings(0),
    )

    # ── Determine which files are already indexed ──────────────────────────────
    already_indexed = get_indexed_sources(vectorstore)
    print(f"[2] Already indexed: {len(already_indexed)} source file(s).")

    # ── Build the target file list ─────────────────────────────────────────────
    if args.scan:
        candidates = [
            f for f in os.listdir(DATA_DIR)
            if f.endswith(".txt") or f.endswith(".csv")
        ]
        target_files = [
            os.path.join(DATA_DIR, f) for f in candidates
            if f not in already_indexed
        ]
        if not target_files:
            print("[ok] All files in /data are already indexed. Nothing to do.")
            sys.exit(0)
        print(f"[3] Found {len(target_files)} new file(s) to index via --scan.")
    else:
        target_files = []
        for p in args.files:
            fname = os.path.basename(p)
            if fname in already_indexed:
                print(f"  [skip] '{fname}' is already indexed.")
            else:
                target_files.append(p)

        if not target_files:
            print("[ok] All specified files are already indexed. Nothing to do.")
            sys.exit(0)

    # ── Load, chunk, and embed each new file ───────────────────────────────────
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    for path in target_files:
        fname = os.path.basename(path)
        print(f"\n  Processing '{fname}'...")
        try:
            if fname.endswith(".csv"):
                docs = load_csv(path)
                print(f"    Loaded {len(docs)} row(s).")
            else:
                docs = load_txt(path)
                print(f"    Loaded {len(docs)} doc(s).")

            chunks = splitter.split_documents(docs)
            print(f"    Split into {len(chunks)} chunk(s).")
            embed_chunks(vectorstore, chunks)
            print(f"  [ok] '{fname}' added to vectorstore.")

        except Exception as e:
            print(f"  [!] Failed to process '{fname}': {e}")

    print(f"\n[DONE] Vectorstore updated at '{DB_DIR}'.")


if __name__ == "__main__":
    main()
