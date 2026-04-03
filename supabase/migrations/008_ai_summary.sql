-- Add ai_summary JSONB column to legislative_items for caching AI-generated summaries.
-- Structure: { "text": "...", "citations": [{ "index": 1, "quote": "...", "source": "..." }], "generated_at": "ISO timestamp" }

alter table legislative_items
    add column ai_summary jsonb;

comment on column legislative_items.ai_summary is
    'Cached AI-generated summary with inline citations. Generated on first view of detail page.';
