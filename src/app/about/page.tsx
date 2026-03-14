export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold">About CivicLens</h1>

      <div className="mt-6 space-y-4 text-sm leading-relaxed text-gray-700">
        <p>
          CivicLens is a civic transparency project that makes government data
          accessible to residents of Bel Air, Maryland (21015). It aggregates
          legislative data from three levels of government — Maryland State,
          Harford County, and the Town of Bel Air — into a single searchable
          interface.
        </p>

        <h2 className="mt-8 text-lg font-semibold text-gray-900">
          What It Does
        </h2>
        <p>
          The <strong>Legislative Tracker</strong> shows active and proposed
          bills, ordinances, resolutions, and policy changes across all three
          jurisdictions. The <strong>Chat</strong> interface lets you ask
          plain-language questions about local law and get sourced answers.
        </p>

        <h2 className="mt-8 text-lg font-semibold text-gray-900">
          Data Sources
        </h2>
        <p>All data comes from public government records:</p>
        <ul className="ml-4 mt-2 list-disc space-y-1 text-gray-600">
          <li>Maryland General Assembly via Open States and LegiScan APIs</li>
          <li>Harford County Council legislation and county code</li>
          <li>Town of Bel Air ordinances, resolutions, and municipal code</li>
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
          State regulations (COMAR — Code of Maryland Regulations) are not yet
          included in this tool due to technical and legal access constraints.
          Questions about state regulatory requirements may receive incomplete
          answers.
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
