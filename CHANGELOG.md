# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Security
- **CRITICAL**: Fix SQL injection in `report_generator.py` with parameterized queries
- **CRITICAL**: Add XSS protection in `ReportPreview.tsx` with DOMPurify sanitization
- Add proper exception logging in `scheduler.py` instead of silent swallowing

### Code Quality
- Fix ESLint warnings (set-state-in-effect, exhaustive-deps)
- Fix Python linting (ruff) in backend
- Fix `formatSql` function idempotency issue

### Frontend
- Optimize DataExplorer UX: inline template editing without modal
- Template name always editable
- Save button for both new and existing templates
- Dirty state tracking for unsaved changes
- Add `isDirty` indicator for pending changes

### Dependencies
- Add `isomorphic-dompurify` for HTML sanitization
- Add `dompurify` type definitions

---

## [0.1.0] - 2026-06-19

### Added
- Initial MVP release of business analysis report tools
- Backend: FastAPI with SQLAlchemy
- Frontend: React + TypeScript + Vite
- Data source management (PostgreSQL, SQLite, OpenGauss, DWS)
- Report definition and generation
- Report preview with Chart.js visualization
- SQL data explorer with syntax highlighting
- Scheduled report execution
- Excel and HTML export formats
