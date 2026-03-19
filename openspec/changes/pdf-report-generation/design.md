## Context

This is Phase 3 of the implementation plan. It can run in parallel with Phase 2 (GTK4 GUI) since both depend only on Phase 1 (core import pipeline) being complete. The report generator reads from the GnuCash book in readonly mode and produces standalone PDF files. The specification (Section 3.7) defines four report types: momsdeklaration, NE-bilaga, grundbok, and huvudbok.

## Goals / Non-Goals

**Goals:**
- Generate four PDF report types from GnuCash data: momsdeklaration, NE-bilaga, grundbok, huvudbok
- A4 paper layout with proper margins, headers, footers, and page numbers
- Momsdeklaration maps account totals to SKV 4700 ruta references (05, 06, 07, 08, 10, 11, 12, 48, 49)
- NE-bilaga maps account totals to INK1 ruta references (R1, R2, R5, R6, R7, B1, B4)
- Grundbok provides chronological journal with page totals and grand totals
- Huvudbok provides per-account ledger with opening/closing balances and subtotals
- Company info (name, org.nummer, address, fiscal year) in report headers
- All monetary totals verified against GnuCash balances

**Non-Goals:**
- SRU file generation (designated as future Phase 5)
- Interactive or editable reports
- Multi-year comparison reports
- Direct electronic submission to Skatteverket

## Decisions

### 1. WeasyPrint for HTML-to-PDF conversion
**Rationale**: WeasyPrint renders HTML/CSS to PDF with excellent A4 layout support via CSS `@page` rules. It handles page breaks, headers, footers, and page counters natively. Already specified in the project dependency list.
**Alternative considered**: ReportLab — lower-level API, harder to maintain templates; wkhtmltopdf — external binary dependency.

### 2. Jinja2 for HTML templating
**Rationale**: Industry standard Python templating engine. Template inheritance (`{% extends "base.html" %}`) allows a shared base layout with report-specific content blocks. Already specified in the project dependency list.
**Alternative considered**: Python string formatting — too fragile for complex HTML layouts.

### 3. Query GnuCash via piecash in readonly mode
**Rationale**: piecash provides a clean ORM over the GnuCash SQLite database. Opening in readonly mode ensures report generation cannot corrupt the book. Account aggregation uses piecash's transaction/split model to sum amounts by account code within the fiscal year date range.
**Alternative considered**: Raw SQLite queries — possible but loses the semantic model piecash provides.

### 4. A4 paper with CSS @page rules
**Rationale**: All Swedish tax and archival documents are A4 format. CSS `@page` rules define margins, page size, and running headers/footers. WeasyPrint supports these rules fully, including `@bottom-center` for page numbers and `@top-right` for company info.

### 5. Company info passed as CompanyInfo dataclass
**Rationale**: Report headers need company name, organisationsnummer, address, and fiscal year. This data comes from the application's config (stored in the rules database config table). Passing it as a dataclass keeps the report generator decoupled from the config storage mechanism.

### 6. Account aggregation by BAS account ranges
**Rationale**: The ruta mappings for momsdeklaration and NE-bilaga aggregate accounts by ranges (e.g., 30xx for revenue, 50xx-69xx for external costs). The report module queries all splits within the fiscal year, groups them by account code, and sums by the defined ranges. This approach is flexible if the user adds new accounts within standard BAS ranges.

## Risks / Trade-offs

- **[Risk] Skatteverket ruta numbers may not match current forms** → Mitigation: Ruta mappings defined as constants in reports.py, easy to update; templates display ruta references alongside values for manual verification
- **[Risk] WeasyPrint rendering differences across versions** → Mitigation: Pin WeasyPrint version in dependencies; test PDF output visually during development
- **[Risk] Large grundbok/huvudbok for busy years** → Mitigation: Page breaks between accounts in huvudbok; page totals in grundbok prevent losing track across pages; WeasyPrint handles multi-page documents well
- **[Trade-off] HTML/CSS templates vs programmatic PDF generation** → Templates are easier to maintain and modify but slightly less precise for complex layouts; acceptable for these report types
