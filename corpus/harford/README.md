# corpus/harford/ — Harford County Documents

Place Harford County PDF documents here along with their JSON sidecar files.

## File naming

Option A — JSON sidecar (recommended):
  `acfr-fy2024.pdf` + `acfr-fy2024.json`

Option B — Filename convention (fallback):
  `harford-financial_report-2024-acfr.pdf`
  (prefix `harford` → COUNTY jurisdiction; second token is doc_type; YYYY token is date)

## Ingest command

```bash
python -m src.ingestion.manual_ingest --dir corpus/harford/
```

## Priority downloads (see docs/planning/corpus-acquisition-plan.md §1)

| Filename | Source URL |
|----------|-----------|
| fy2026-operating-budget.pdf | harfordcountymd.gov/3864/Approved-FY26-Budget |
| acfr-fy2024.pdf | harfordcountymd.gov/DocumentCenter/View/26925/June-30-2024-ACFR-PDF |
| zoning-code-current.pdf | harfordcountymd.gov/DocumentCenter/View/2257/Zoning-Code-PDF |
| subdivision-regulations-current.pdf | harfordcountymd.gov/DocumentCenter/View/2256/Subdivision-Regulations-PDF |
| fy2025-budget-message.pdf | harfordcountymd.gov/DocumentCenter/View/25925/FY2025-Budget-Message-from-Harford-County-Executive-Bob-Cassilly |
