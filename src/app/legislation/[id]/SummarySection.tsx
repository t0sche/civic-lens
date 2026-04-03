"use client";

import { useState, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";

interface Citation {
  index: number;
  quote: string;
  source: string;
}

interface SummaryData {
  text: string;
  citations: Citation[];
  generated_at: string;
  cached: boolean;
  no_sources?: boolean;
  error?: string;
}

export default function SummarySection({
  itemId,
  sourceUrl,
}: {
  itemId: string;
  sourceUrl: string | null;
}) {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/legislation/${itemId}/summary`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || `Failed to load summary (${res.status})`);
      }
      const data: SummaryData = await res.json();
      setSummary(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate summary"
      );
    } finally {
      setLoading(false);
    }
  }, [itemId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // Loading state
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <div>
            <p className="text-sm font-medium text-gray-700">
              Generating AI Summary...
            </p>
            <p className="mt-0.5 text-xs text-gray-400">
              Analyzing source documents and creating a plain-language summary
              with citations.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
        <p className="text-sm font-medium text-amber-800">
          Unable to generate summary
        </p>
        <p className="mt-1 text-xs text-amber-600">{error}</p>
        <button
          onClick={fetchSummary}
          className="mt-3 rounded-md bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800 transition hover:bg-amber-200"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (!summary) return null;

  // No sources available
  if (summary.no_sources) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-6">
        <p className="text-sm text-gray-600">{summary.text}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">AI-Generated Summary</h2>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          {summary.cached && <span>Cached</span>}
          <span>
            Generated{" "}
            {new Date(summary.generated_at).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
        </div>
      </div>

      {/* Summary content */}
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="prose prose-sm max-w-none text-gray-800 [&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:my-2 [&_ol]:my-2 [&_li]:my-0.5">
          <ReactMarkdown
            components={{
              // Highlight citation markers as interactive elements
              p: ({ children, ...props }) => {
                return <p {...props}>{processChildren(children)}</p>;
              },
              li: ({ children, ...props }) => {
                return <li {...props}>{processChildren(children)}</li>;
              },
            }}
          >
            {summary.text}
          </ReactMarkdown>
        </div>

        {/* Source link within summary */}
        {sourceUrl && (
          <div className="mt-4 border-t border-gray-100 pt-3">
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline"
            >
              <svg
                className="h-3.5 w-3.5"
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
              Read the full original document
            </a>
          </div>
        )}
      </div>

      {/* Citations */}
      {summary.citations.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="mb-3 text-sm font-semibold text-gray-700">
            Citations from Source Document
          </h3>
          <div className="space-y-3">
            {summary.citations.map((citation) => (
              <div
                key={citation.index}
                id={`citation-${citation.index}`}
                className="rounded-md border border-gray-100 bg-gray-50 p-3 transition hover:border-gray-200"
              >
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 inline-flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-700">
                    {citation.index}
                  </span>
                  <div className="min-w-0 flex-1">
                    <blockquote className="text-xs italic text-gray-600">
                      &ldquo;{citation.quote}&rdquo;
                    </blockquote>
                    <p className="mt-1 text-[10px] text-gray-400">
                      {citation.source}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Process React children to make [N] citation markers interactive.
 */
function processChildren(children: React.ReactNode): React.ReactNode {
  if (!children) return children;

  if (typeof children === "string") {
    return processCitationText(children);
  }

  if (Array.isArray(children)) {
    return children.map((child, i) => {
      if (typeof child === "string") {
        return <span key={i}>{processCitationText(child)}</span>;
      }
      return child;
    });
  }

  return children;
}

function processCitationText(text: string): React.ReactNode {
  const parts = text.split(/(\[\d+\])/g);
  if (parts.length === 1) return text;

  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const num = match[1];
      return (
        <a
          key={i}
          href={`#citation-${num}`}
          className="mx-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-blue-100 text-[9px] font-bold text-blue-700 no-underline transition hover:bg-blue-200"
          title={`See citation ${num}`}
          onClick={(e) => {
            e.preventDefault();
            const el = document.getElementById(`citation-${num}`);
            if (el) {
              el.scrollIntoView({ behavior: "smooth", block: "center" });
              el.classList.add("border-blue-300", "bg-blue-50");
              setTimeout(() => {
                el.classList.remove("border-blue-300", "bg-blue-50");
              }, 2000);
            }
          }}
        >
          {num}
        </a>
      );
    }
    return part;
  });
}
