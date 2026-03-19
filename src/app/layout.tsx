import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "CivicLens — Bel Air, MD",
  description:
    "Plain-language access to the laws that affect you. Track legislation and ask questions about local, county, and state law in Bel Air, Maryland.",
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <header className="border-b border-gray-200 bg-white">
          <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-xl font-semibold tracking-tight">
              CivicLens
            </Link>
            <div className="flex gap-6 text-sm">
              <Link href="/" className="hover:text-blue-600">
                Dashboard
              </Link>
              <Link href="/chat" className="hover:text-blue-600">
                Ask a Question
              </Link>
              <Link href="/about" className="hover:text-blue-600">
                About
              </Link>
            </div>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="border-t border-gray-200 bg-white py-6 text-center text-xs text-gray-500">
          <p>
            CivicLens is not a law firm and does not provide legal advice.
            Information is provided for educational purposes only.
          </p>
          <p className="mt-1">
            Data sourced from Maryland General Assembly, Harford County, and
            Town of Bel Air public records.
          </p>
          <p className="mt-1">
            Legislative data provided by{" "}
            <a
              href="https://legiscan.com"
              className="underline hover:text-gray-700"
              target="_blank"
              rel="noopener noreferrer"
            >
              LegiScan
            </a>
            {" "}and licensed under{" "}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              className="underline hover:text-gray-700"
              target="_blank"
              rel="noopener noreferrer"
            >
              Creative Commons Attribution 4.0
            </a>
            .
          </p>
        </footer>
      </body>
    </html>
  );
}
