# Requirements Document: Swedish Bookkeeping Automation for Enskild Firma

**Version**: 1.0
**Date**: 2026-03-19
**Author**: Requirements Analyst (Claude)
**Stakeholder**: Repository owner (sole proprietor)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context](#2-business-context)
3. [Goals and Objectives](#3-goals-and-objectives)
4. [Scope](#4-scope)
5. [Stakeholders](#5-stakeholders)
6. [User Personas / Actors](#6-user-personas--actors)
7. [Functional Requirements](#7-functional-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Data Requirements](#9-data-requirements)
10. [Integration Requirements](#10-integration-requirements)
11. [Constraints](#11-constraints)
12. [Assumptions](#12-assumptions)
13. [Dependencies](#13-dependencies)
14. [Risks](#14-risks)
15. [Success Criteria](#15-success-criteria)
16. [Open Questions](#16-open-questions)
17. [Appendices](#17-appendices)

---

## 1. Executive Summary

### Problem
A sole proprietor running an enskild firma in Sweden currently relies on a volunteer (using paid software) to handle bookkeeping, VAT reporting, and income tax preparation. The volunteer will not be available indefinitely. Manual data entry into GnuCash is tedious and error-prone, especially given that the vast majority of transactions are repetitive month-to-month. The proprietor needs an affordable, self-sufficient bookkeeping workflow.

### Proposed Solution
An open-source toolchain that:
1. **Imports** bank transaction CSVs into a double-entry bookkeeping application (GnuCash or equivalent)
2. **Assists categorization** by remembering recurring transaction-to-account mappings against the BAS 2023 kontoplan
3. **Detects and prevents duplicate transactions** when importing overlapping date ranges
4. **Generates PDF reports** summarizing the values needed for the yearly momsdeklaration (VAT return) and NE-bilaga (income tax attachment)

### Key Success Criteria
- Eliminate manual transaction entry entirely
- Reduce categorization effort through learned mappings
- Produce trustworthy, printable reports that map directly to Swedish tax form fields
- Fully open-source, running on Debian-based Linux

---

## 2. Business Context

### Background and Rationale
- The company is an **enskild firma** (Swedish sole proprietorship)
- Revenue comes from **consulting invoices** (with 25% moms/VAT) and **YouTube ad revenue** (via Google AdSense, paid in USD but reported in SEK on bank statements)
- The business currently operates near **break-even** — revenue roughly covers service/subscription expenses
- A volunteer currently handles all bookkeeping using a paid tool, producing reports from bank statements. This person will eventually no longer be available
- The proprietor has used GnuCash but finds manual data entry impractical for the repetitive nature of the transactions
- Bookkeeping records have been maintained for 10+ years, meeting the 7-year legal retention requirement

### Current State
1. Proprietor exports bank transactions as CSV from online banking
2. CSV is sent to volunteer
3. Volunteer enters data into a paid accounting tool
4. Volunteer produces reports for VAT and income tax
5. Proprietor manually fills in Skatteverket forms using the report values

### Desired State
1. Proprietor exports bank transactions as CSV from online banking
2. CSV is imported into an open-source bookkeeping application (automated)
3. Transactions are categorized with assistance from learned mappings (semi-automated)
4. Proprietor verifies categorization in a GUI
5. PDF reports are generated with values mapped to tax form fields
6. Proprietor fills in Skatteverket forms using the printed reports

---

## 3. Goals and Objectives

### Business Goals
- **Self-sufficiency**: Proprietor can complete the full bookkeeping cycle without external help
- **Cost elimination**: Replace paid accounting tool with open-source solution
- **Compliance**: Continue meeting Swedish bokföringslagen requirements

### User Goals
- **Minimal data entry**: Import transactions from CSV, never type them manually
- **Low cognitive load**: Recurring transactions should be auto-suggested, not re-categorized each time
- **Trust through verification**: GUI-based review of all categorizations before committing
- **Clear tax preparation**: PDF reports that make filling in tax forms straightforward

### Measurable Success Criteria
- 100% of bank transactions importable from CSV without manual entry
- 90%+ of recurring transactions auto-suggested correctly after initial categorization
- Zero duplicate transactions when importing overlapping date ranges
- PDF reports contain all values needed for momsdeklaration and NE-bilaga
- Full workflow completable by the proprietor without external assistance

### KPIs
- Time spent on monthly bookkeeping (target: under 30 minutes for a typical month)
- Number of manual corrections needed per import batch
- Accuracy of suggested categorizations over time

---

## 4. Scope

### In Scope

- **CSV import tool**: Parse bank transaction exports and load into bookkeeping application
- **Duplicate detection**: Prevent the same transaction from being imported twice
- **BAS 2023 account mapping**: Use the standard Swedish chart of accounts
- **Transaction categorization assistance**: Rule-based mapping that remembers previous categorizations (no AI/ML)
- **GUI verification**: Ability to review and correct categorizations in a graphical application
- **PDF report generation**: Reports summarizing values for momsdeklaration and NE-bilaga
- **Legal archiving format**: PDF output suitable for 7-year record retention
- **Linux support**: Debian/Ubuntu compatible

### Out of Scope

- AI/ML-based transaction classification
- Automatic filing with Skatteverket
- Invoice generation or management
- Payroll processing
- Multi-user or multi-company support
- Mobile or web interface
- Bank API integration (direct bank feeds)
- Migration of historical GnuCash data (starting fresh)

### Future Considerations (Phase 2+)

- **SRU file generation**: Digital upload to Skatteverket (the proprietor wants this but will not use it until trust in the solution is established)
- Savings account tracking (currently unused due to revenue level)
- Internet and phone expense tracking (not yet a business expense)

---

## 5. Stakeholders

| Stakeholder | Role | Interest | Decision Authority |
|---|---|---|---|
| Proprietor | Sole user, sole decision-maker | Usable, trustworthy bookkeeping | Full authority |
| Volunteer (current) | Temporary bookkeeper | Smooth handover | Advisory |
| Skatteverket | Tax authority | Correct VAT and income tax reporting | Defines form requirements |

---

## 6. User Personas / Actors

### Primary User: The Proprietor
- **Technical proficiency**: Comfortable with Linux CLI and GUI applications; not an accounting expert
- **Accounting knowledge**: Basic understanding of double-entry bookkeeping; uncertain about which BAS accounts to use for specific transactions
- **Usage pattern**: Monthly or batched every few months; intensive use in January for annual VAT and tax filing
- **Motivation**: Reduce tedium of repetitive data entry; gain independence from volunteer
- **Tolerance for complexity**: Prefers simplicity; willing to learn but wants the tool to guide, not require expertise

---

## 7. Functional Requirements

### 7.1 CSV Import

| ID | Requirement | Priority |
|---|---|---|
| F-IMP-01 | **Import bank transaction CSV files** in the format exported by the proprietor's bank (semicolon-delimited, UTF-8, Swedish date format YYYY-MM-DD) | Must-have |
| F-IMP-02 | **Parse all CSV fields**: Bokforingsdatum, Valutadatum, Verifikationsnummer, Text, Belopp, Saldo | Must-have |
| F-IMP-03 | **Handle decimal amounts** with period as decimal separator and 3 decimal places (e.g., `867.150` = 867.15 SEK) | Must-have |
| F-IMP-04 | **Detect and reject duplicate transactions** when importing overlapping date ranges, using Verifikationsnummer as unique identifier | Must-have |
| F-IMP-05 | **Support importing multiple months** in a single CSV or across multiple CSVs without duplication | Must-have |
| F-IMP-06 | **Report import results**: number of transactions imported, number of duplicates skipped, any parsing errors | Should-have |

### 7.2 Chart of Accounts (BAS 2023)

| ID | Requirement | Priority |
|---|---|---|
| F-COA-01 | **Load the BAS 2023 kontoplan** from the provided `bas2023.csv` | Must-have |
| F-COA-02 | **Support both huvudkonton and underkonton** (main accounts and sub-accounts) | Must-have |
| F-COA-03 | **Present a simplified subset** of commonly needed accounts for a small enskild firma (filtering by the BAS "grundlaggande bokforing" marker) while allowing access to the full plan | Should-have |
| F-COA-04 | **Allow the user to select** which accounts are active/relevant for their business to reduce clutter | Could-have |

### 7.3 Transaction Categorization

| ID | Requirement | Priority |
|---|---|---|
| F-CAT-01 | **Map each imported transaction to a BAS account** (debit and credit sides for double-entry bookkeeping) | Must-have |
| F-CAT-02 | **Suggest account mappings** for transactions based on previously categorized transactions with matching text patterns | Must-have |
| F-CAT-03 | **Store categorization rules** persistently — when the user categorizes "Spotify" as konto 6540, future transactions with the same text auto-suggest the same mapping | Must-have |
| F-CAT-04 | **Always require user confirmation** — suggestions are proposals, never auto-committed | Must-have |
| F-CAT-05 | **Allow easy correction** — if a categorization is wrong, the user can change it, and the updated mapping should be remembered | Must-have |
| F-CAT-06 | **Handle VAT splitting** — for transactions that include moms, automatically split into the net amount and the VAT portion (e.g., 25% moms on consulting income) | Must-have |
| F-CAT-07 | **No AI/ML integration** — categorization assistance must be purely rule-based (pattern matching on transaction text) | Must-have |

### 7.4 GUI Verification

| ID | Requirement | Priority |
|---|---|---|
| F-GUI-01 | **Display imported transactions** in a list/table with all fields visible | Must-have |
| F-GUI-02 | **Show suggested and assigned BAS account** for each transaction | Must-have |
| F-GUI-03 | **Allow the user to accept, change, or override** the account assignment for any transaction | Must-have |
| F-GUI-04 | **Provide account selection** via searchable dropdown or similar control showing account number and description | Should-have |
| F-GUI-05 | **Highlight uncategorized transactions** that need attention | Should-have |
| F-GUI-06 | **Show running balance** and allow comparison against the bank statement Saldo field for reconciliation (avstamning) | Should-have |
| F-GUI-07 | **Support batch operations** — if the user is importing several months, allow processing all at once or month-by-month | Could-have |

### 7.5 Report Generation

| ID | Requirement | Priority |
|---|---|---|
| F-RPT-01 | **Generate a momsdeklaration summary PDF** with all values needed to fill in the yearly VAT return, mapped to the correct form fields | Must-have |
| F-RPT-02 | **Generate an NE-bilaga summary PDF** with all values needed to fill in the income tax attachment for enskild firma | Must-have |
| F-RPT-03 | **Include field references** — each value in the report should indicate which field/ruta on the Skatteverket form it corresponds to | Must-have |
| F-RPT-04 | **Generate a grundbok (journal)** — chronological list of all transactions with their account mappings, suitable for archiving | Must-have |
| F-RPT-05 | **Generate a huvudbok (general ledger)** — transactions organized by account, suitable for archiving | Should-have |
| F-RPT-06 | **PDF format** for all reports, suitable for printing on A4 | Must-have |
| F-RPT-07 | **Annual reports** covering the full fiscal year (Jan 1 – Dec 31) | Must-have |
| F-RPT-08 | Reports must be **readable and verifiable** — clear layout with totals, subtotals, and cross-references | Should-have |

### 7.6 SRU File Generation (Future Phase)

| ID | Requirement | Priority |
|---|---|---|
| F-SRU-01 | **Generate SRU files** compatible with Skatteverket's digital filing system | Could-have |
| F-SRU-02 | **Support NE-bilaga SRU format** | Could-have |
| F-SRU-03 | **Support momsdeklaration SRU format** | Could-have |

### 7.7 Business Rules

| ID | Rule | Description |
|---|---|---|
| BR-01 | **Double-entry principle** | Every transaction must have equal debit and credit entries |
| BR-02 | **VAT rate for consulting** | Consulting invoices use 25% moms (standard Swedish rate) |
| BR-03 | **YouTube revenue** | YouTube ad revenue arrives as SEK deposits; no Swedish VAT applies (reverse charge / outside-EU service) |
| BR-04 | **Fiscal year** | Calendar year: January 1 – December 31 |
| BR-05 | **Simplified yearly VAT** | VAT is reported and paid once annually (forenklad arsmoms), reported in January for the previous year |
| BR-06 | **Duplicate detection** | Verifikationsnummer is unique per transaction and used as the deduplication key |
| BR-07 | **Archiving retention** | All bookkeeping records must be retained for at least 7 years per bokforingslagen |

---

## 8. Non-Functional Requirements

### Performance
| ID | Requirement |
|---|---|
| NF-PERF-01 | CSV import of 500 transactions should complete in under 10 seconds |
| NF-PERF-02 | GUI should remain responsive with up to 1,000 transactions loaded |
| NF-PERF-03 | PDF report generation should complete in under 30 seconds |

### Security
| ID | Requirement |
|---|---|
| NF-SEC-01 | All data stored locally on the user's machine — no cloud dependencies |
| NF-SEC-02 | No transmission of financial data over the network |
| NF-SEC-03 | File permissions should protect bookkeeping data from other system users |

### Availability & Reliability
| ID | Requirement |
|---|---|
| NF-REL-01 | Application must work fully offline |
| NF-REL-02 | Data integrity: no partial imports — if import fails, no transactions should be committed |
| NF-REL-03 | Categorization rules must survive application restarts and upgrades |

### Usability
| ID | Requirement |
|---|---|
| NF-USE-01 | A user with basic Linux and bookkeeping knowledge should be able to complete the full workflow without consulting external documentation |
| NF-USE-02 | Account selection should show both account number and Swedish description |
| NF-USE-03 | Error messages should be clear and actionable |

### Maintainability
| ID | Requirement |
|---|---|
| NF-MNT-01 | Solution should be maintainable by a single developer (the proprietor) |
| NF-MNT-02 | Minimal external dependencies to reduce breakage risk |
| NF-MNT-03 | BAS kontoplan should be updatable when new versions are released |

---

## 9. Data Requirements

### 9.1 Data Entities

#### Bank Transaction (imported from CSV)
| Field | Type | Description |
|---|---|---|
| Bokforingsdatum | Date (YYYY-MM-DD) | Booking date |
| Valutadatum | Date (YYYY-MM-DD) | Value date |
| Verifikationsnummer | String | Unique transaction identifier from the bank |
| Text | String | Transaction description |
| Belopp | Decimal | Amount in SEK (negative = debit/expense, positive = credit/income) |
| Saldo | Decimal | Running balance after transaction |

#### BAS Account
| Field | Type | Description |
|---|---|---|
| Kontonummer | Integer (4 digits) | Account number per BAS 2023 |
| Kontonamn | String | Account description (Swedish) |
| Kontotyp | Enum | Huvudkonto or Underkonto |
| Grundlaggande | Boolean | Whether marked as basic bookkeeping account (black square marker) |
| K2-applicable | Boolean | Whether applicable under K2 rules |

#### Categorization Rule
| Field | Type | Description |
|---|---|---|
| Pattern | String | Text pattern to match against transaction Text field |
| Debit Account | Integer | BAS account number for the debit side |
| Credit Account | Integer | BAS account number for the credit side |
| VAT Rate | Decimal | Applicable VAT rate (0%, 6%, 12%, 25%) |
| Last Used | Date | When this rule was last applied |

#### Journal Entry (Verifikation)
| Field | Type | Description |
|---|---|---|
| Verifikationsnummer | String | From bank transaction |
| Datum | Date | Booking date |
| Beskrivning | String | Transaction text |
| Rows | List | One or more debit/credit lines with account and amount |

### 9.2 Data Volume
- ~200–400 transactions per year (estimated from ~6/month sample)
- 6–12 CSV imports per year (monthly or batched)
- ~20–30 active BAS accounts out of ~1,300 in the full plan
- Growing at a stable rate (small business, not scaling rapidly)

### 9.3 Data Quality
- Bank CSV is the authoritative source — Saldo field can be used for reconciliation
- Verifikationsnummer must be unique and is trusted as a deduplication key
- Amounts may have 3 decimal places (trailing zero) — must be parsed correctly

### 9.4 Data Retention
- All journal entries and reports must be retained for a minimum of 7 years
- PDF reports serve as the archival format
- Application data (categorization rules) should also be backed up

### 9.5 Data Migration
- No migration of historical GnuCash data required — starting fresh
- Historical records (10 years) exist in other formats and are retained separately

---

## 10. Integration Requirements

### GnuCash (or equivalent)
| ID | Requirement |
|---|---|
| I-GC-01 | Import transactions into GnuCash's data format (XML or SQLite backend) |
| I-GC-02 | Map BAS 2023 accounts to GnuCash's chart of accounts structure |
| I-GC-03 | Support GnuCash's double-entry transaction model |
| I-GC-04 | Alternatively: if a lighter-weight open-source bookkeeping tool is more suitable, it must provide equivalent GUI verification capabilities |

### PDF Generation
| ID | Requirement |
|---|---|
| I-PDF-01 | Generate well-formatted A4 PDF documents |
| I-PDF-02 | Include headers, dates, page numbers, and company information |
| I-PDF-03 | Use a PDF library available in Debian/Ubuntu repositories |

---

## 11. Constraints

### Technical Constraints
- **Platform**: Debian-based Linux (Ubuntu or similar)
- **Licensing**: All components must be open-source (no paid tools)
- **No cloud services**: Everything runs locally
- **No AI/ML**: Categorization must be deterministic and rule-based
- **Package availability**: Prefer software available in standard Debian/Ubuntu repositories or easily installable via standard package managers (apt, pip, etc.)

### Business Constraints
- **Zero budget**: This is a hobby/exploratory project
- **Single maintainer**: The proprietor must be able to maintain and update the solution
- **Timeline**: No deadline — "done when done"
- **Trust-building**: The proprietor will manually verify all outputs against the current volunteer's reports before relying on the tool

### Regulatory/Compliance Constraints
- **Bokforingslagen (Bookkeeping Act)**: 7-year record retention
- **Mervardesskatt (VAT)**: Correct application of Swedish VAT rates (25%, 12%, 6%, 0%)
- **NE-bilaga**: Income and expenses must map to the correct fields in Skatteverket's NE form
- **Momsdeklaration**: VAT summary must map to the correct fields in Skatteverket's VAT form

---

## 12. Assumptions

| ID | Assumption | Impact if Wrong |
|---|---|---|
| A-01 | The bank CSV format will remain stable over time | Import parser would need updating |
| A-02 | Verifikationsnummer is globally unique across all bank exports | Duplicate detection would fail |
| A-03 | All transactions flow through a single bank account | Multi-account support would be needed |
| A-04 | The proprietor's business only uses standard VAT rates (25%, 0%) | Additional VAT handling would be needed |
| A-05 | GnuCash can be configured to use the BAS 2023 kontoplan | Alternative tool would be needed |
| A-06 | The BAS 2023 account structure is sufficient (no custom accounts needed) | Customization features would be required |
| A-07 | YouTube revenue does not require Swedish VAT handling | VAT rules for the transaction would need revisiting |
| A-08 | The CSV uses period as decimal separator with 3 decimal places | Amount parsing logic would need adjustment |

---

## 13. Dependencies

| ID | Dependency | Type | Status |
|---|---|---|---|
| D-01 | GnuCash (or alternative) available on Debian/Ubuntu | Software | Available in repos |
| D-02 | BAS 2023 kontoplan data (`bas2023.csv`) | Data | Provided in repository |
| D-03 | Bank CSV export capability | External service | Available |
| D-04 | Skatteverket form field specifications for NE-bilaga | Reference documentation | Needs research |
| D-05 | Skatteverket form field specifications for momsdeklaration | Reference documentation | Needs research |
| D-06 | SRU file format specification (future phase) | Reference documentation | Needs research when relevant |

---

## 14. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | BAS 2023 CSV is complex to parse (irregular format with metadata rows, markers, and mixed columns) | High | Medium | Invest time in a robust parser; validate against known accounts |
| R-02 | GnuCash import may have limitations or undocumented quirks | Medium | Medium | Prototype the import early; consider alternative tools |
| R-03 | Skatteverket form fields may change between tax years | Low | Medium | Design report templates to be configurable |
| R-04 | Proprietor may miscategorize transactions without the volunteer's expertise | Medium | High | Provide clear account descriptions; consider a "review checklist" feature |
| R-05 | Bank changes CSV export format | Low | High | Isolate the CSV parser so it can be updated independently |
| R-06 | Scope creep — tendency to add features beyond the core workflow | Medium | Medium | Strict phasing; get core working before adding SRU, etc. |
| R-07 | VAT rules for YouTube/international income may be more complex than assumed | Medium | Medium | Research Skatteverket guidelines for digital services income early |

---

## 15. Success Criteria

### Minimum Viable Product (MVP)
- [ ] Bank CSV can be imported without manual data entry
- [ ] Duplicate transactions are detected and skipped
- [ ] Transactions can be categorized against BAS 2023 accounts in a GUI
- [ ] Categorization rules are remembered for recurring transactions
- [ ] A grundbok (journal) PDF can be generated
- [ ] A momsdeklaration summary PDF can be generated with field references
- [ ] An NE-bilaga summary PDF can be generated with field references
- [ ] The entire workflow runs on Debian-based Linux with open-source tools only

### Acceptance Validation
- The proprietor processes one quarter of real transactions through the tool
- Output is compared against the volunteer's reports for the same period
- Values match to the oere (smallest currency unit)

---

## 16. Open Questions

| ID | Question | Needed By | Owner |
|---|---|---|---|
| OQ-01 | What are the exact field numbers (rutor) for the NE-bilaga that need to be populated? | Design phase | Solution Architect |
| OQ-02 | What are the exact field numbers for the momsdeklaration? | Design phase | Solution Architect |
| OQ-03 | Which specific BAS accounts does the proprietor currently use? (Can be determined from volunteer's existing reports) | Implementation | Proprietor |
| OQ-04 | Does GnuCash support BAS 2023 out of the box, or does the chart of accounts need to be imported manually? | Design phase | Solution Architect |
| OQ-05 | What is the exact parsing logic for the BAS 2023 CSV? (Complex multi-column format with markers and metadata) | Implementation | Solution Architect |
| OQ-06 | Are there specific legal format requirements for the grundbok/huvudbok archive PDFs? | Design phase | Solution Architect |
| OQ-07 | How should YouTube income be treated for VAT purposes? (Likely outside scope of Swedish VAT, but needs confirmation) | Design phase | Proprietor / Skatteverket |
| OQ-08 | GnuCash version currently packaged for Ubuntu — does it support SQLite backend and programmatic import? | Design phase | Solution Architect |

---

## 17. Appendices

### A. Glossary

| Swedish Term | English | Description |
|---|---|---|
| Enskild firma | Sole proprietorship | Business form where the individual is the business |
| Moms / Mervardesskatt | VAT | Value Added Tax, standard rate 25% in Sweden |
| Momsdeklaration | VAT return | Annual (simplified) or periodic VAT filing |
| NE-bilaga | NE attachment | Income tax form attachment for sole proprietors |
| BAS 2023 | BAS 2023 | Standard Swedish chart of accounts |
| Kontoplan | Chart of accounts | Structured list of all bookkeeping accounts |
| Bokforingslagen | Bookkeeping Act | Swedish law governing accounting requirements |
| Grundbok | Journal | Chronological record of all transactions |
| Huvudbok | General ledger | Transactions organized by account |
| Verifikation | Voucher/entry | A documented bookkeeping transaction |
| Avstamning | Reconciliation | Verifying book balance matches bank balance |
| Forenklad arsmoms | Simplified yearly VAT | Annual VAT reporting for small businesses |
| SRU | SRU file | Digital format for filing with Skatteverket |
| Skatteverket | Swedish Tax Agency | Government authority for tax collection |
| Kontonummer | Account number | BAS account identifier |
| Bokforingsdatum | Booking date | Date the transaction was recorded |
| Valutadatum | Value date | Date the transaction was effective |
| Belopp | Amount | Transaction amount in SEK |
| Saldo | Balance | Account balance after transaction |

### B. Sample CSV Format

```csv
Bokföringsdatum;Valutadatum;Verifikationsnummer;Text;Belopp;Saldo
2026-01-28;2026-01-28;123990558;Description;-100.000;867.150
```

- **Delimiter**: Semicolon (`;`)
- **Encoding**: UTF-8
- **Date format**: YYYY-MM-DD
- **Amount format**: Decimal with period separator, 3 decimal places
- **Negative amounts**: Expenses/debits (outgoing money)
- **Positive amounts**: Income/credits (incoming money)

### C. Typical BAS Accounts for a Small Consulting/Content Enskild Firma

*(To be confirmed during implementation, but likely includes:)*

| Account | Description | Usage |
|---|---|---|
| 1930 | Foretagskonto / checkrakningskonto | Business bank account |
| 2610 | Utgaende moms 25% | Outgoing VAT on consulting |
| 2640 | Ingaende moms | Incoming VAT on purchases |
| 2650 | Momsredovisningskonto | VAT settlement account |
| 3010 | Forsaljning tjanster, 25% moms | Consulting revenue |
| 3040 | Forsaljning tjanster, momsfri | YouTube revenue (no Swedish VAT) |
| 6212 | Programvarulicenser | Software subscriptions |
| 6540 | IT-tjanster | IT services |
| 6570 | Bankkostnader | Bank fees |
| 8300 | Ranteintakter | Interest income (if any) |

### D. Reference Documents

- BAS 2023 kontoplan: `bas2023.csv` (in repository)
- Sample bank export: `account.csv` (in repository)
- Skatteverket NE-bilaga: [skatteverket.se](https://www.skatteverket.se)
- Skatteverket momsdeklaration: [skatteverket.se](https://www.skatteverket.se)
- SRU file format specification: [skatteverket.se](https://www.skatteverket.se)
