-- CivicLens: Add unique constraints for Silver layer upserts
-- Migration: 004_silver_layer_unique_constraints
-- Date: 2026-03-16
--
-- The normalization pipeline upserts legislative_items and code_sections
-- using ON CONFLICT. Postgres requires matching unique constraints.

alter table legislative_items
    add constraint uq_legitem_source
    unique (source_id, jurisdiction, body);

alter table code_sections
    add constraint uq_codesec_source
    unique (code_source, chapter, section);
