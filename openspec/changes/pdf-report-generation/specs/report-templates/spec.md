## ADDED Requirements

### Requirement: Base template with shared A4 layout
The system SHALL provide a `bokforing/templates/base.html` Jinja2 template that defines the shared A4 page layout, including CSS `@page` rules, company info header, page numbering footer, and content blocks for report-specific templates to extend.

#### Scenario: A4 page size
- **WHEN** the base template is rendered to PDF
- **THEN** the page size is A4 (210mm x 297mm) with appropriate margins

#### Scenario: Company info header
- **WHEN** a report extends the base template with company_info provided
- **THEN** the header displays company name, organisationsnummer, address, and fiscal year

#### Scenario: Page number footer
- **WHEN** a report renders to multiple pages
- **THEN** each page footer shows "Sida X av Y" using CSS counters

#### Scenario: Content block for inheritance
- **WHEN** a report-specific template extends base.html
- **THEN** it can override the `{% block content %}` and `{% block title %}` blocks

### Requirement: Momsdeklaration template
The system SHALL provide a `bokforing/templates/momsdeklaration.html` Jinja2 template that extends base.html and displays the momsdeklaration summary as a table of ruta numbers, descriptions, and amounts.

#### Scenario: Ruta table layout
- **WHEN** the momsdeklaration template is rendered with ruta data
- **THEN** it displays a table with columns: Ruta, Beskrivning, Belopp (SEK)

#### Scenario: SKV 4700 reference
- **WHEN** the momsdeklaration template is rendered
- **THEN** it includes a reference to "SKV 4700" and the fiscal year period

### Requirement: NE-bilaga template
The system SHALL provide a `bokforing/templates/ne_bilaga.html` Jinja2 template that extends base.html and displays the NE-bilaga summary with resultaträkning and balansräkning sections.

#### Scenario: Resultaträkning section
- **WHEN** the NE-bilaga template is rendered
- **THEN** it shows rutor R1, R2, R5, R6, R7 with descriptions and amounts

#### Scenario: Balansräkning section
- **WHEN** the NE-bilaga template is rendered
- **THEN** it shows rutor B1 and B4 with descriptions and amounts

#### Scenario: INK1 reference
- **WHEN** the NE-bilaga template is rendered
- **THEN** it includes a reference to "INK1 NE-bilaga" and the fiscal year

### Requirement: Grundbok template
The system SHALL provide a `bokforing/templates/grundbok.html` Jinja2 template that extends base.html and displays the chronological journal as a table with page breaks and totals.

#### Scenario: Transaction table columns
- **WHEN** the grundbok template is rendered with transaction data
- **THEN** it displays columns: Verifikation, Datum, Text, Konto, Debet, Kredit

#### Scenario: Page totals
- **WHEN** the grundbok template renders across page boundaries
- **THEN** it includes running page totals for Debet and Kredit columns

#### Scenario: Grand totals
- **WHEN** the grundbok template finishes rendering all transactions
- **THEN** it displays grand totals for Debet and Kredit at the end

### Requirement: Huvudbok template
The system SHALL provide a `bokforing/templates/huvudbok.html` Jinja2 template that extends base.html and displays the general ledger grouped by account.

#### Scenario: Account section headers
- **WHEN** the huvudbok template renders an account section
- **THEN** it shows the account number and name as a section header

#### Scenario: Opening and closing balances
- **WHEN** an account section is rendered
- **THEN** it shows "Ingående balans" at the top and "Utgående balans" at the bottom

#### Scenario: Transaction rows within account
- **WHEN** transactions are listed for an account
- **THEN** each row shows: Datum, Verifikation, Text, Debet, Kredit

#### Scenario: Page break between accounts
- **WHEN** the huvudbok has many accounts
- **THEN** CSS rules allow page breaks between account sections (via `page-break-before` or `break-before`)

### Requirement: Print-optimized CSS
The system SHALL include CSS styles in the templates optimized for print/PDF output, including: monospace or tabular number fonts for amounts, proper table borders, no background colors that waste ink, and sufficient contrast for archival scanning.

#### Scenario: Amount formatting
- **WHEN** amounts are displayed in any template
- **THEN** they are right-aligned with consistent decimal formatting

#### Scenario: Table readability
- **WHEN** tables are rendered in the PDF
- **THEN** they have visible borders, adequate row spacing, and alternating row shading (light gray) for readability
