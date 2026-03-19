## Why

The proprietor needs PDF reports for tax filing (momsdeklaration, NE-bilaga) and legal archiving (grundbok, huvudbok). Swedish law (bokföringslagen) requires a chronological journal (grundbok) and a general ledger (huvudbok) to be archived for 7 years. The momsdeklaration and NE-bilaga summaries map GnuCash account totals directly to Skatteverket form fields (ruta numbers), enabling accurate manual transcription during tax filing.

## What Changes

- Implement `bokforing/reports.py` with `generate_report(report_type, gnucash_book_path, fiscal_year, output_path, company_info) -> Path`
- Query GnuCash book via piecash for transaction data and account balances within a fiscal year
- Aggregate amounts by BAS account ranges and map to Skatteverket ruta references
- Create HTML/CSS templates in `bokforing/templates/`: `base.html`, `momsdeklaration.html`, `ne_bilaga.html`, `grundbok.html`, `huvudbok.html`
- Use Jinja2 for HTML templating and WeasyPrint for HTML-to-PDF conversion
- Generate A4-formatted PDFs with company info headers, page numbers, and fiscal year references

## Capabilities

### New Capabilities
- `report-generation`: GnuCash data querying, account aggregation by BAS ranges, ruta mapping for momsdeklaration (SKV 4700) and NE-bilaga (INK1), and PDF generation via WeasyPrint
- `report-templates`: Jinja2 HTML/CSS templates for A4 print layout with shared base template, per-report templates, headers, footers, and page numbering

### Modified Capabilities

## Impact

- **Code**: New module `bokforing/reports.py`, new directory `bokforing/templates/` with 5 HTML files, new tests in `tests/test_reports.py`
- **Dependencies**: Requires WeasyPrint (>=60.0) and Jinja2 (>=3.1), both already specified in the project's dependency list
- **Data**: Reads from GnuCash SQLite book (via piecash, readonly), produces PDF files in the output directory
- **Other components**: No changes to existing modules; depends on the same GnuCash book and BAS account structure used by other components
