# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Swedish bookkeeping/accounting project** in the requirements and design phase. It is not yet a software codebase — it uses the OpenSpec workflow to move from requirements gathering through solution architecture to implementation.

## Domain Context

- **Language/Locale**: Swedish accounting domain. CSV data uses semicolon delimiters, Swedish date format (YYYY-MM-DD), and Swedish decimal notation (period as thousands separator in the CSV amounts).
- **BAS 2023**: `bas2023.csv` contains the Swedish BAS 2023 chart of accounts (kontoplan), which is the standard account numbering system used in Swedish bookkeeping.
- **account.csv**: Sample bank transaction export with columns: Bokföringsdatum, Valutadatum, Verifikationsnummer, Text, Belopp, Saldo.

## Workflow

This project uses the **OpenSpec spec-driven workflow** via Claude Code skills and slash commands (`/opsx:*`). The workflow phases are:

1. **Requirements Analyst** (`personas/ANALYST.md`) — Elicits requirements and produces a `REQUIREMENTS.md`
2. **Solution Architect** (`personas/SOLUTION_ARCHITECT.md`) — Transforms requirements into a `SPECIFICATION.md`
3. **Implementation** — Via OpenSpec changes, tasks, and apply workflow

### OpenSpec Commands

- `/opsx:new` — Start a new change
- `/opsx:continue` — Create next artifact for a change
- `/opsx:ff` — Fast-forward through all artifacts at once
- `/opsx:apply` — Implement tasks from a change
- `/opsx:verify` — Verify implementation matches artifacts
- `/opsx:archive` — Archive a completed change
- `/opsx:explore` — Thinking/exploration mode

### OpenSpec Directory Structure

- `openspec/config.yaml` — Project configuration
- `openspec/specs/` — Main specifications
- `openspec/changes/` — Active changes with artifacts
- `openspec/changes/archive/` — Completed changes

## Personas

When loaded as system prompts, the personas define structured roles:

- **ANALYST.md**: Produces `REQUIREMENTS.md` through stakeholder Q&A. Uses a detailed question framework covering discovery, scope, functional, technical, quality, and risk dimensions.
- **SOLUTION_ARCHITECT.md**: Reads `REQUIREMENTS.md`, engages in design discussion, and produces `SPECIFICATION.md` with architecture, data models, APIs, and implementation plan.
