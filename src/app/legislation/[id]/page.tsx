import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { createServerClient } from "@/lib/supabase-client";
import { statusColor, jurisdictionLabel } from "@/lib/badges";
import SummarySection from "./SummarySection";

interface PageProps {
  params: Promise<{ id: string }>;
}

async function fetchItem(id: string) {
  const db = createServerClient();
  const { data, error } = await db
    .from("legislative_items")
    .select("*")
    .eq("id", id)
    .single();
  if (error) return null;
  return data;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  const item = await fetchItem(id);
  if (!item) return { title: "Not Found — CivicLens" };
  return {
    title: `${item.source_id}: ${item.title} — CivicLens`,
    description: `AI-generated summary and analysis of ${item.source_id}: ${item.title}`,
  };
}

export default async function LegislationDetailPage({ params }: PageProps) {
  const { id } = await params;

  const item = await fetchItem(id);
  if (!item) {
    notFound();
  }

  const jLabel = jurisdictionLabel(item.jurisdiction);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Back link */}
      <a
        href="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 19l-7-7 7-7"
          />
        </svg>
        Back to Legislative Tracker
      </a>

      {/* Header */}
      <div className="mb-8">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span
            className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${jLabel.className}`}
          >
            {jLabel.text}
          </span>
          <span
            className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${statusColor(item.status)}`}
          >
            {item.status.replace(/_/g, " ")}
          </span>
          <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
            {item.item_type.replace(/_/g, " ")}
          </span>
          <span className="text-sm text-gray-400">{item.source_id}</span>
        </div>

        <h1 className="text-2xl font-bold leading-tight">{item.title}</h1>

        {/* Metadata */}
        <div className="mt-4 space-y-2 text-sm text-gray-600">
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            <span>
              <span className="font-medium text-gray-700">Body:</span>{" "}
              {item.body}
            </span>
            {item.introduced_date && (
              <span>
                <span className="font-medium text-gray-700">Introduced:</span>{" "}
                {item.introduced_date}
              </span>
            )}
            {item.last_action_date && (
              <span>
                <span className="font-medium text-gray-700">Last action:</span>{" "}
                {item.last_action_date}
              </span>
            )}
          </div>
          {item.last_action && (
            <p className="text-gray-500">{item.last_action}</p>
          )}
          {item.sponsors && item.sponsors.length > 0 && (
            <p>
              <span className="font-medium text-gray-700">Sponsors:</span>{" "}
              {item.sponsors.join(", ")}
            </p>
          )}
          {item.tags && item.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {item.tags.map((tag: string) => (
                <span
                  key={tag}
                  className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Source link */}
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 transition hover:bg-blue-100"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
            View Original Source
          </a>
        )}
      </div>

      {/* AI Summary Section */}
      <SummarySection itemId={id} sourceUrl={item.source_url} />

      {/* Disclaimer */}
      <div className="mt-8 rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-gray-500">
        <p>
          This summary is AI-generated for educational purposes only and is not
          legal advice. Citations reference passages from official source
          documents. Always consult the{" "}
          {item.source_url ? (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              original source
            </a>
          ) : (
            "original source"
          )}{" "}
          and a qualified attorney for legal guidance.
        </p>
      </div>
    </div>
  );
}
