import config from "../../../civic-lens.config.json";

function formatJurisdictionCount(count: number): string {
  switch (count) {
    case 1:
      return "one";
    case 2:
      return "two";
    case 3:
      return "three";
    default:
      return String(count);
  }
}

function formatJurisdictionList(jurisdictions: string[]): string {
  if (jurisdictions.length === 0) return "";
  if (jurisdictions.length === 1) return jurisdictions[0];
  if (jurisdictions.length === 2) {
    return `${jurisdictions[0]} and ${jurisdictions[1]}`;
  }
  const allButLast = jurisdictions.slice(0, -1).join(", ");
  const last = jurisdictions[jurisdictions.length - 1];
  return `${allButLast}, and ${last}`;
}

export default function AboutPage() {
  const { locality, zip } = config;
  const jurisdictions: string[] = [];
  if (locality.state) jurisdictions.push(`${locality.state.name} State`);
  if (locality.county) jurisdictions.push(locality.county.name);
  if (locality.municipal) jurisdictions.push(locality.municipal.name);
  const jurisdictionCount = jurisdictions.length;
  const jurisdictionCountWord = formatJurisdictionCount(jurisdictionCount);
  const jurisdictionList = formatJurisdictionList(jurisdictions);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold">About CivicLens</h1>

      <div className="mt-6 space-y-4 text-sm leading-relaxed text-gray-700">
        <p>
          CivicLens is a civic transparency project that makes government data
          accessible to residents of {`${locality.name} (${zip})`}. It aggregates
          legislative data from {jurisdictionCountWord}{" "}
          {jurisdictionCount === 1 ? "level" : "levels"} of government —{" "}
          {jurisdictionList} — into a single searchable interface.
        </p>

        <h2 className="mt-8 text-lg font-semibold text-gray-900">
          What It Does
        </h2>
        <p>
          The <strong>Legislative Tracker</strong> shows active and proposed
          bills, ordinances, resolutions, and policy changes across all{" "}
          {jurisdictionCountWord}{" "}
          {jurisdictionCount === 1 ? "jurisdiction" : "jurisdictions"}. The{" "}
          <strong>Chat</strong> interface lets you ask plain-language questions
          about local law and get sourced answers.
        </p>

        <h2 className="mt-8 text-lg font-semibold text-gray-900">
          Data Sources
        </h2>
        <p>All data comes from public government records:</p>
        <ul className="ml-4 mt-2 list-disc space-y-1 text-gray-600">
          <li>{`${locality.state.name} General Assembly via Open States and LegiScan APIs`}</li>
          {locality.county && (
            <li>{`${locality.county.name} legislation and county code`}</li>
          )}
          {locality.municipal && (
            <li>{`${locality.municipal.name} ordinances, resolutions, and municipal code`}</li>
          )}
          <li>Meeting agendas and minutes from boards and commissions</li>
        </ul>
        <p className="mt-2 text-xs text-gray-500">
          Municipal and county codes are sourced from General Code&apos;s
          eCode360 platform. Data refreshes automatically every 6–24 hours
          depending on the source.
        </p>

        <h2 className="mt-8 text-lg font-semibold text-gray-900">
          Important Disclaimers
        </h2>
        <p>
          CivicLens is <strong>not a law firm</strong> and does not provide
          legal advice. The information presented here is for educational
          purposes only. Laws and regulations may change between data refreshes.
          Always verify critical information with the relevant government body
          and consult a qualified attorney for legal guidance.
        </p>
        <p>
          State regulations are not yet included in this tool due to technical
          and legal access constraints. Questions about state regulatory
          requirements may receive incomplete answers.
        </p>

        <h2 className="mt-8 text-lg font-semibold text-gray-900">
          Open Source
        </h2>
        <p>
          CivicLens is open source under the MIT license. The architecture is
          designed to be forkable for other jurisdictions.{" "}
          <a
            href="https://github.com/YOUR_USERNAME/civiclens"
            className="text-blue-600 hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            View on GitHub
          </a>
        </p>
      </div>
    </div>
  );
}
