/** Shared badge styling utilities for status and jurisdiction display. */

export function statusColor(status: string): string {
  const colors: Record<string, string> = {
    INTRODUCED: "bg-blue-100 text-blue-800",
    IN_COMMITTEE: "bg-yellow-100 text-yellow-800",
    PASSED_ONE_CHAMBER: "bg-indigo-100 text-indigo-800",
    ENACTED: "bg-green-100 text-green-800",
    APPROVED: "bg-green-100 text-green-800",
    EFFECTIVE: "bg-green-100 text-green-800",
    VETOED: "bg-red-100 text-red-800",
    REJECTED: "bg-red-100 text-red-800",
    EXPIRED: "bg-gray-100 text-gray-800",
    PENDING: "bg-amber-100 text-amber-800",
    TABLED: "bg-orange-100 text-orange-800",
    UNKNOWN: "bg-gray-100 text-gray-600",
  };
  return colors[status] || colors.UNKNOWN;
}

export function jurisdictionLabel(jurisdiction: string): {
  text: string;
  className: string;
} {
  const labels: Record<string, { text: string; className: string }> = {
    STATE: { text: "State", className: "bg-purple-100 text-purple-800" },
    COUNTY: { text: "County", className: "bg-teal-100 text-teal-800" },
    MUNICIPAL: { text: "Municipal", className: "bg-sky-100 text-sky-800" },
  };
  return (
    labels[jurisdiction] || {
      text: jurisdiction,
      className: "bg-gray-100 text-gray-800",
    }
  );
}
