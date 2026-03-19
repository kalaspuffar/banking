## Context

Users export CSV transaction data from their bank, potentially with overlapping date ranges between exports. The GnuCash writer stores the bank's Verifikationsnummer in each transaction's `num` field. Before any categorization work is done, the system must identify which incoming transactions already exist in the book so they can be skipped.

## Goals / Non-Goals

**Goals:**
- Detect duplicate transactions by comparing Verifikationsnummer against GnuCash transaction `num` fields
- Run before categorization in the import pipeline to avoid wasted effort on already-imported transactions
- Open the GnuCash book in readonly mode to avoid any risk of corruption during the check
- Return both new and duplicate lists so the caller can report how many were skipped

**Non-Goals:**
- Fuzzy matching or similarity-based deduplication (exact match only)
- Handling transactions that lack a Verifikationsnummer (these are passed through as new)
- Deduplication across multiple GnuCash books
- Modifying the GnuCash book in any way

## Decisions

### 1. Open GnuCash book in readonly mode
**Rationale**: The duplicate check is a read-only operation. Opening with `piecash.open_book(path, readonly=True)` avoids any risk of accidental writes or lock conflicts. The GnuCash GUI can even be open simultaneously during this step.

### 2. Extract all existing `num` fields into a set for O(1) lookup
**Rationale**: The book contains ~200-400 transactions per year, growing over time. Loading all `num` values into a Python set provides instant lookup for each incoming transaction. Memory usage is trivial even for many years of data.

### 3. Exact string comparison on Verifikationsnummer vs `num`
**Rationale**: The bank assigns unique numeric IDs to each transaction. The writer stores these verbatim in the `num` field. Exact string comparison is sufficient and avoids false positives from fuzzy matching.

### 4. Run before categorization in the pipeline
**Rationale**: Categorization involves rule lookup and potentially user interaction. Filtering duplicates first means only genuinely new transactions enter that stage, saving time and reducing noise.

## Risks / Trade-offs

- **[Risk] Verifikationsnummer is missing or empty for some transactions** → Mitigation: Treat transactions with empty/None Verifikationsnummer as new (never match as duplicate). Document this behavior.
- **[Risk] GnuCash book is locked by the GUI** → Mitigation: readonly mode should not conflict with GUI locks, but if it does, raise a clear error message.
- **[Trade-off] Loading all `num` values into memory** → Acceptable for the expected data volume (~2000 transactions over 5+ years). Would need revisiting only for very large books.
