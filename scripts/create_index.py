"""
scripts/create_index.py
-----------------------
One-off utility to build (or rebuild) the ChromaDB vector store from the
raw SOP documents in the /data directory.

Run from the project root:
    python scripts/create_index.py
"""

import os
import sys
import time
import shutil

# Allow imports from the project root when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
DATA_DIR      = "./data"
DB_DIR        = "./db"
CHUNK_SIZE    = 500
CHUNK_OVERLAP = 75

# ── 1. Wipe existing vectorstore (prevent duplicate embeddings) ─────────────────
if os.path.exists(DB_DIR):
    print(f"[1/4] Clearing existing vectorstore at '{DB_DIR}'...")
    shutil.rmtree(DB_DIR)
else:
    print(f"[1/4] No existing vectorstore found — starting fresh.")

# ── 2. Load all .txt files from /data ─────────────────────────────────────────
print("[2/4] Loading source documents...")
all_docs = []
txt_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".txt")]

if not txt_files:
    raise RuntimeError("No .txt files found in /data directory.")

for filename in txt_files:
    path = os.path.join(DATA_DIR, filename)
    try:
        loader = TextLoader(path, encoding="utf-8")
        docs   = loader.load()
        print(f"  [ok] Loaded '{filename}' ({len(docs)} doc(s))")
        all_docs.extend(docs)
    except Exception as e:
        print(f"  [!] Skipping '{filename}' - {e}")

if not all_docs:
    raise RuntimeError("No documents were loaded. Check your /data directory.")

print(f"  [ok] Total: {len(all_docs)} document(s) loaded from {len(txt_files)} file(s).")

# ── 3. Chunk documents ─────────────────────────────────────────────────────────
print(f"[3/4] Splitting into chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")
splitter   = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)
doc_chunks = splitter.split_documents(all_docs)
print(f"  [ok] {len(doc_chunks)} chunks created across {len(all_docs)} page(s).")

# ── 4. Embed & persist to Chroma ──────────────────────────────────────────────
print("[4/4] Embedding and persisting to Chroma vectorstore...")
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

BATCH_SIZE  = 50  # stay under 100 requests/min free tier limit
BATCH_DELAY = 65  # seconds to wait between batches

vectorstore = None
for i in range(0, len(doc_chunks), BATCH_SIZE):
    batch       = doc_chunks[i:i + BATCH_SIZE]
    batch_num   = (i // BATCH_SIZE) + 1
    total_batches = (len(doc_chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  Embedding batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

    for attempt in range(3):
        try:
            if vectorstore is None:
                vectorstore = Chroma.from_documents(batch, embeddings, persist_directory=DB_DIR)
            else:
                vectorstore.add_documents(batch)
            break
        except Exception as e:
            if attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"  [!] Error on attempt {attempt+1}: {e}")
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [!] Failed after 3 attempts. Skipping batch {batch_num}.")
                print(f"  Error: {e}")

    if i + BATCH_SIZE < len(doc_chunks):
        print(f"  Waiting {BATCH_DELAY}s to avoid rate limit...")
        time.sleep(BATCH_DELAY)

print(f"  [ok] Vectorstore saved to '{DB_DIR}'.")

# ── Smoke test ─────────────────────────────────────────────────────────────────
print("\n-- Smoke Test ----------------------------------------------------------")
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

test_queries = [
    "What is the procedure to request an EWH FortiToken?",
    "How do I reset a FortiToken?",
]

for query in test_queries:
    results = retriever.invoke(query)
    print(f"\nQuery : {query}")
    if results:
        print(f'Top result snippet:\n  "{results[0].page_content[:300]}..."')
    else:
        print("  [!] No results returned - check if the files was ingested correctly.")

print("\n[DONE] Ingestion complete. The agent is ready to handle FortiToken emails.")
