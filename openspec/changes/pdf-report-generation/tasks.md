## 1. Report Module Setup and GnuCash Data Queries

- [ ] 1.1 Create `bokforing/reports.py` with the `generate_report(report_type, gnucash_book_path, fiscal_year, output_path, company_info) -> Path` entry point function and report type dispatch logic
- [ ] 1.2 Implement GnuCash data querying via piecash: open book in readonly mode, fetch all transactions/splits within the fiscal year date range (2025-01-01 to 2025-12-31 for fiscal_year=2025)
- [ ] 1.3 Implement account aggregation by BAS ranges: sum split amounts grouped by account code, with helper functions to aggregate by account prefix (e.g., 30xx) and account range (e.g., 50xx-69xx)

## 2. Momsdeklaration Report

- [ ] 2.1 Implement momsdeklaration ruta mapping: define SKV 4700 ruta constants mapping ruta numbers to account codes/ranges (ruta 05→3010, ruta 08→3040, ruta 10→2610, ruta 48→2640, ruta 49→computed)
- [ ] 2.2 Implement data preparation function that queries GnuCash and returns a dictionary of ruta→amount for the momsdeklaration template

## 3. NE-bilaga Report

- [ ] 3.1 Implement NE-bilaga ruta mapping: define INK1 ruta constants mapping ruta references to account ranges (R1→30xx, R2→37xx-39xx, R5→50xx-69xx, R6→79xx, R7→computed, B1→2010 opening, B4→2010 closing)
- [ ] 3.2 Implement data preparation function that queries GnuCash and returns a dictionary of ruta→amount for the NE-bilaga template, including opening/closing balance calculation for account 2010

## 4. Grundbok and Huvudbok Reports

- [ ] 4.1 Implement grundbok data preparation: query all transactions for the fiscal year, flatten to split-level rows (verifikation, datum, text, konto, debet, kredit), sort by date then verifikationsnummer, compute grand totals
- [ ] 4.2 Implement huvudbok data preparation: query all accounts with activity in the fiscal year, for each account compute opening balance, list transactions, compute closing balance and subtotals, sort by account number

## 5. HTML/CSS Templates

- [ ] 5.1 Create `bokforing/templates/base.html` with A4 CSS `@page` rules (210mm x 297mm, margins), company info header block, "Sida X av Y" page number footer using CSS counters, and `{% block title %}` / `{% block content %}` for inheritance
- [ ] 5.2 Create `bokforing/templates/momsdeklaration.html` extending base.html, with a ruta table (Ruta, Beskrivning, Belopp) and SKV 4700 reference
- [ ] 5.3 Create `bokforing/templates/ne_bilaga.html` extending base.html, with resultaträkning section (R1, R2, R5, R6, R7) and balansräkning section (B1, B4), and INK1 reference
- [ ] 5.4 Create `bokforing/templates/grundbok.html` extending base.html, with transaction table (Verifikation, Datum, Text, Konto, Debet, Kredit) and grand totals row
- [ ] 5.5 Create `bokforing/templates/huvudbok.html` extending base.html, with per-account sections (header, opening balance, transaction rows, closing balance), page-break CSS between accounts

## 6. PDF Generation

- [ ] 6.1 Implement the Jinja2 template rendering pipeline: configure Jinja2 environment with the templates directory, render the appropriate template with report data and company_info context
- [ ] 6.2 Implement WeasyPrint HTML-to-PDF conversion: take rendered HTML string, convert to A4 PDF, write to output_path, return the Path

## 7. Tests

- [ ] 7.1 Create `tests/test_reports.py` with a piecash test fixture that creates a GnuCash book with known transactions across multiple BAS accounts (1930, 2010, 2610, 2640, 3010, 3040, 6212, 6540)
- [ ] 7.2 Write tests verifying momsdeklaration ruta values match expected totals from the test fixture data
- [ ] 7.3 Write tests verifying NE-bilaga ruta values (R1, R5, R7, B1, B4) match expected totals
- [ ] 7.4 Write tests verifying grundbok grand totals: total debet equals total kredit (balanced)
- [ ] 7.5 Write tests verifying huvudbok account balances: opening + debets - credits = closing for each account
- [ ] 7.6 Write tests verifying PDF file generation: each report type produces a non-empty PDF file at the expected path
