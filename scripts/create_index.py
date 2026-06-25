"""
scripts/create_index.py
-----------------------
One-off utility to build (or rebuild) the ChromaDB vector store from the
raw SOP documents and CSV data files in the /data directory.

Run from the project root:
    python scripts/create_index.py
"""

import os
import sys
import time
import shutil
import csv

# Allow imports from the project root when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
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
    print(f"[1/4] No existing vectorstore found - starting fresh.")

# ── 2. Load all .txt and .csv files from /data ────────────────────────────────
print("[2/4] Loading source documents...")
all_docs  = []
txt_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".txt")]
csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]

if not txt_files and not csv_files:
    raise RuntimeError("No .txt or .csv files found in /data directory.")

# Load .txt files
for filename in txt_files:
    path = os.path.join(DATA_DIR, filename)
    try:
        loader = TextLoader(path, encoding="utf-8")
        docs   = loader.load()
        print(f"  [ok] Loaded '{filename}' ({len(docs)} doc(s))")
        all_docs.extend(docs)
    except Exception as e:
        print(f"  [!] Skipping '{filename}' - {e}")

# Load .csv files — each row becomes one Document with a descriptive text block
for filename in csv_files:
    path = os.path.join(DATA_DIR, filename)
    try:
        csv_docs = []
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                # Skip completely empty rows
                if not any(v.strip() for v in row.values() if v):
                    continue

                # Build a readable text block from column: value pairs
                lines = [f"{col}: {val}" for col, val in row.items() if val and val.strip()]
                content = "\n".join(lines)

                doc = Document(
                    page_content=content,
                    metadata={
                        "source": filename,
                        "row": i + 2,  # 1-indexed, +1 for header
                        "sales_order": row.get("Sales Order Number", "").strip(),
                        "customer": row.get("Customer Company", "").strip(),
                        "end_customer": row.get("End Customer Company", "").strip(),
                        "country": row.get("End Customer Installation Country", "").strip(),
                        "service_type": row.get("Service Type", "").strip(),
                    },
                )
                csv_docs.append(doc)

        print(f"  [ok] Loaded '{filename}' ({len(csv_docs)} row(s) as documents)")
        all_docs.extend(csv_docs)
    except Exception as e:
        print(f"  [!] Skipping '{filename}' - {e}")

if not all_docs:
    raise RuntimeError("No documents were loaded. Check your /data directory.")

print(f"  [ok] Total: {len(all_docs)} document(s) loaded from "
      f"{len(txt_files)} .txt file(s) and {len(csv_files)} .csv file(s).")

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
    "What is the IP address for Aptiv Japan circuit?",
    "Find the circuit details for NEV-SO20207951",
]

for query in test_queries:
    results = retriever.invoke(query)
    print(f"\nQuery : {query}")
    if results:
        print(f'Top result snippet:\n  "{results[0].page_content[:300]}..."')
    else:
        print("  [!] No results returned - check if the files was ingested correctly.")

print("\n[DONE] Ingestion complete. The agent is ready to handle NOC emails and circuit lookups.")
