# Reliable Data Provenance Implementation Plan

> **For agentic workers:** Use this approved plan task-by-task; report each task before continuing.

**Goal:** Make every decision input traceable to an authoritative source or an explicit farm-provided value, and show that evidence clearly in the UI.

**Architecture:** Keep source metadata in a versioned JSON catalog served by FastAPI. The frontend will render that catalog alongside every FarmProfile field, climate coverage and recommendation rationale. Gridded or regional products remain contextual evidence and never silently replace field measurements.

**Tech Stack:** Python, FastAPI, JSON reference data, React/TypeScript, pytest, Node test runner.

**Spec:** User-approved proposal in the conversation on 2026-11-15.

## Global Constraints

- Do not fabricate climate, soil, crop calendar or farm measurements.
- NASA POWER is historical/near-real-time context, never a future weather forecast.
- Preserve UNKNOWN when required evidence is absent or outside source coverage.
- Show citation, temporal coverage, spatial scale and limitations for sourced values.

## Review Focus

- Malformed or incomplete source catalog must return a safe server error without stack trace.
- A source with coarse spatial scope must not be presented as a field measurement.
- User-supplied farm data must remain distinguishable from sourced estimates.
- Climate period and UI date bounds must follow the actual retrieved artifact.
- Missing citations must remain visible as unavailable evidence, not hidden.

### Task 1: Source Catalog API

**Files:** `data/reference/data_sources.json`, `backend/app/main.py`, `backend/tests/test_api.py`.

- [x] Add authoritative source metadata with citation URL, fields, coverage, scale and limitations.
- [x] Test `GET /api/data-sources` returns validated source records.
- [x] Implement the endpoint and run its tests.

### Task 2: Complete Farm Profile and Evidence UI

**Files:** `frontend/src/App.tsx`, `frontend/src/types.ts`, `frontend/src/api/client.ts`, `frontend/src/rotation.css`, frontend tests.

- [x] Test data-source response parsing and field completeness where practical.
- [x] Render all FarmProfile fields and expose input/source status for each.
- [x] Render source citations, climate period and spatial/temporal caveats.
- [x] Run frontend tests and production build.

### Task 3: Crop Evidence Gaps

**Files:** `data/reference/crop_catalog.json`, `data/reference/rotation_rules.json`, relevant backend/data-science tests.

- [x] Add crop-specific calendar or water evidence only when the source supports the crop, region and dates.
- [x] Preserve UNKNOWN for gaps that do not have matching evidence.
- [x] Test source scope, validity period and evidence-backed outcomes.

### Task 4: Full Verification and Handoff

- [x] Run backend/Data Science tests, frontend tests and production build.
- [x] Review generated data and citations; exclude runtime caches.
- [x] Report findings and wait for review before commit/push/PR.
