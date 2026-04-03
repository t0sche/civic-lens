/**
 * Locality configuration loader for CivicLens.
 *
 * Reads civic-lens.config.json at build time (Next.js bundles JSON imports).
 * All UI components and server-side code should import from here
 * instead of hardcoding locality-specific strings.
 */

import config from "../../civic-lens.config.json";

// ─── Types ────────────────────────────────────────────────────────────

export interface StateConfig {
  name: string;
  abbrev: string;
  body: string;
  openstates_jurisdiction: string;
  legiscan_state_id: number;
}

export interface ScraperConfig {
  [key: string]: { code?: string; url?: string };
}

export interface CountyConfig {
  name: string;
  body: string;
  scrapers: ScraperConfig;
}

export interface MunicipalConfig {
  name: string;
  body: string;
  website: string;
  scrapers: ScraperConfig;
}

export interface DisplayConfig {
  title: string;
  subtitle: string;
  description: string;
  footer_attribution: string;
  example_questions: string[];
}

export interface LocalityConfig {
  zip: string;
  locality: {
    name: string;
    state: StateConfig;
    county: CountyConfig | null;
    municipal: MunicipalConfig | null;
  };
  display: DisplayConfig;
}

// ─── Accessors ────────────────────────────────────────────────────────

const locality = config as LocalityConfig;

export function getLocality(): LocalityConfig {
  return locality;
}

export function getStateConfig(): StateConfig {
  return locality.locality.state;
}

export function getCountyConfig(): CountyConfig | null {
  return locality.locality.county ?? null;
}

export function getMunicipalConfig(): MunicipalConfig | null {
  return locality.locality.municipal ?? null;
}

export function getDisplayConfig(): DisplayConfig {
  return locality.display;
}

/**
 * Build a list of configured jurisdiction names for display.
 */
export function getJurisdictionNames(): string[] {
  const names: string[] = [locality.locality.state.name];
  if (locality.locality.county) names.push(locality.locality.county.name);
  if (locality.locality.municipal) names.push(locality.locality.municipal.name);
  return names;
}

/**
 * Build a system prompt locality description for RAG.
 */
export function buildLocalityDescription(): string {
  const parts: string[] = [];
  parts.push(`${locality.locality.state.name} State`);
  if (locality.locality.county) parts.push(locality.locality.county.name);
  if (locality.locality.municipal) parts.push(locality.locality.municipal.name);
  return parts.join(", ");
}
