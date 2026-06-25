"""
src/tools/CircuitLookup.py
--------------------------
Direct CSV lookup for circuit details — no LLM, no vectorstore.

Searches all CSV files in /data for a match against:
  - Sales Order Number  (e.g. NEV-SO20207951)
  - Customer Circuit Reference
  - Provider Circuit Reference

Returns a formatted text block ready to inject into the writer prompt.
"""

import os
import csv
import re
import logging

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")

# Columns used as search keys (case-insensitive substring match)
SEARCH_COLUMNS = [
    "Sales Order Number",
    "Customer Circuit Reference",
    "Provider Circuit Reference",
]

# Columns to include in the formatted output
OUTPUT_COLUMNS = [
    "Sales Order Number",
    "Customer Company",
    "End Customer Company",
    "End Customer Installation Address",
    "End Customer Installation Country",
    "Service Type",
    "CPE Model",
    "CPE Serial",
    "CPE Management",
    "CPE Maintenance",
    "IP Address LAN",
    "IP Address WAN",
    "Provider Company",
    "Provider Circuit Reference",
    "Customer Circuit Reference",
    "Purchase Order Type",
    "Customer RFS/Termination Date",
    "Notes",
]


def _load_all_csv_rows() -> list[dict]:
    """Load every row from every CSV in /data into a list of dicts."""
    rows = []
    for fname in os.listdir(DATA_DIR):
        if not fname.lower().endswith(".csv"):
            continue
        path = os.path.join(DATA_DIR, fname)
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if any(v.strip() for v in row.values() if v):
                        row["_source_file"] = fname
                        rows.append(row)
        except Exception as e:
            logger.warning(f"CircuitLookup: could not read '{fname}': {e}")
    return rows


def _extract_tokens(text: str) -> list[str]:
    """
    Extract candidate reference tokens from email text.
    Looks for:
      - NEV-* style IDs  (e.g. NEV-SO20207951, NEV9200238)
        Handles fused text like 'NEV-SO2020660Singtel' by stripping trailing letters.
      - Provider ticket patterns  (alphanumeric strings 6-20 chars)
        This catches things like INC000026948985, 90140376, CAF1405768083
    """
    tokens = []

    # NEV- prefixed IDs: grab full fused token then strip trailing non-ID letters
    raw_nev = re.findall(r'\bNEV[-A-Za-z0-9]+', text, re.IGNORECASE)
    for token in raw_nev:
        # All NEV IDs end in digits — strip any trailing alpha chars caused by missing spaces
        clean = re.sub(r'[A-Za-z]+$', '', token)
        if clean:
            tokens.append(clean)

    # Generic alphanumeric references (at least 6 chars, mixed letters+digits or all digits)
    tokens += re.findall(r'\b(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]{6,20}\b', text)

    # Deduplicate, preserve order
    seen = set()
    result = []
    for t in tokens:
        tl = t.upper()
        if tl not in seen:
            seen.add(tl)
            result.append(t)
    return result


def _format_row(row: dict) -> str:
    """Format a matched CSV row as a readable text block."""
    lines = ["CIRCUIT DETAILS (from internal database):"]
    lines.append("-" * 40)
    for col in OUTPUT_COLUMNS:
        val = row.get(col, "").strip()
        if val and val.upper() not in ("N/A", "TBA", ""):
            lines.append(f"  {col}: {val}")
    lines.append(f"  Source file: {row.get('_source_file', 'unknown')}")
    lines.append("-" * 40)
    return "\n".join(lines)


def lookup_circuit_from_email(email_body: str, email_subject: str = "") -> str:
    """
    Search all CSV files for circuit records matching references found in the email.

    Parameters
    ----------
    email_body    : Full text of the email body
    email_subject : Subject line (also searched)

    Returns a formatted string of matched circuit details, or empty string if none found.
    """
    search_text = f"{email_subject} {email_body}"
    tokens = _extract_tokens(search_text)

    if not tokens:
        logger.debug("CircuitLookup: no reference tokens found in email.")
        return ""

    logger.info(f"CircuitLookup: searching for tokens: {tokens}")

    rows = _load_all_csv_rows()
    matched = []
    seen_orders = set()

    for token in tokens:
        token_upper = token.upper()
        for row in rows:
            # Avoid duplicate matches for the same sales order
            sales_order = row.get("Sales Order Number", "").strip().upper()
            if sales_order in seen_orders:
                continue

            for col in SEARCH_COLUMNS:
                cell = row.get(col, "").strip().upper()
                if cell and token_upper in cell:
                    matched.append(row)
                    seen_orders.add(sales_order)
                    logger.info(
                        f"CircuitLookup: matched token '{token}' in column '{col}' "
                        f"-> {row.get('Sales Order Number', '?')} | "
                        f"Customer: {row.get('Customer Company', '?')} | "
                        f"Provider: {row.get('Provider Company', '?')}"
                    )
                    break  # no need to check other columns for this row

    if not matched:
        logger.info(f"CircuitLookup: no circuit records found for tokens: {tokens}")
        return ""

    logger.info(f"CircuitLookup: found {len(matched)} matching circuit record(s).")
    return "\n\n".join(_format_row(r) for r in matched)
