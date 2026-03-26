# corpus/belair/ — Town of Bel Air Documents

Place Town of Bel Air PDF documents here along with their JSON sidecar files.

## File naming

Option A — JSON sidecar (recommended):
  `fy2026-final-budget.pdf` + `fy2026-final-budget.json`

Option B — Filename convention (fallback):
  `belair-budget-2026-final.pdf`
  (prefix `belair` → MUNICIPAL jurisdiction; second token is doc_type; YYYY token is date)

## Ingest command

```bash
python -m src.ingestion.manual_ingest --dir corpus/belair/
```

## Priority downloads (see docs/planning/corpus-acquisition-plan.md §1)

| Filename | Source URL |
|----------|-----------|
| fy2026-final-budget.pdf | belairmd.org/DocumentCenter/View/6958/RES-1252-25-FY26-Final-Budget-Binder1 |
| comprehensive-plan-2022.pdf | belairmd.org/DocumentCenter/View/92/Comprehensive-Plan-Book |
| police-annual-report-2023.pdf | belairmd.org/DocumentCenter/View/6950/2023 |
| zoning-quick-reference.pdf | belairmd.org/DocumentCenter/View/1328/QUICK-REFERENCE-GUIDE-FOR-ZONING-DISTRICTS |
