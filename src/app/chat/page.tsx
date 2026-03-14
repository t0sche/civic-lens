"use client";

import { useState, useRef, useEffect } from "react";

/**
 * Chat interface for asking questions about local law.
 *
 * @spec CHAT-UI-001, CHAT-UI-002
 */

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  model?: string;
  tier?: string;
}

interface Source {
  index: number;
  section_path: string | null;
  jurisdiction: string;
  source_type: string;
  similarity: number;
}

const EXAMPLE_QUESTIONS = [
  "What are the fence regulations in Bel Air?",
  "Can I run a home business in a residential zone?",
  "What are the noise ordinance hours?",
  "What bills are being considered in the Maryland General Assembly that affect Harford County?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(query?: string) {
    const message = query || input.trim();
    if (!message || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await response.json();

      if (response.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.answer,
            sources: data.sources,
            model: data.model,
            tier: data.tier,
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.error || "Sorry, something went wrong. Please try again.",
          },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Unable to connect to the server. Please check your connection and try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col px-4 py-8" style={{ minHeight: "calc(100vh - 140px)" }}>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Ask About Local Law</h1>
        <p className="mt-1 text-sm text-gray-600">
          Ask plain-language questions about laws, ordinances, and regulations
          affecting Bel Air, MD across state, county, and municipal government.
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto pb-4">
        {messages.length === 0 && (
          <div className="py-8">
            <p className="mb-4 text-sm text-gray-500">
              Try one of these example questions:
            </p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSubmit(q)}
                  className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-sm text-gray-700 shadow-sm transition hover:border-blue-300 hover:shadow-md"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-4 py-3 ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "border border-gray-200 bg-white text-gray-800"
              }`}
            >
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {msg.content}
              </div>

              {/* Source citations */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 border-t border-gray-100 pt-2">
                  <p className="text-xs font-medium text-gray-500">Sources:</p>
                  <div className="mt-1 space-y-1">
                    {msg.sources.map((src) => (
                      <div
                        key={src.index}
                        className="text-xs text-gray-400"
                      >
                        [{src.index}] {src.section_path || "Unknown source"}{" "}
                        <span className="text-gray-300">
                          ({src.jurisdiction})
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Model tier indicator (subtle, for debugging) */}
              {msg.tier && (
                <div className="mt-2 text-right">
                  <span
                    className={`inline-block rounded px-1.5 py-0.5 text-[10px] ${
                      msg.tier === "frontier"
                        ? "bg-purple-50 text-purple-400"
                        : "bg-gray-50 text-gray-400"
                    }`}
                  >
                    {msg.tier === "frontier" ? "Deep analysis" : "Quick answer"}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <div className="h-2 w-2 animate-pulse rounded-full bg-blue-400" />
                Searching laws and generating answer...
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="sticky bottom-0 mt-4 border-t border-gray-200 bg-gray-50 pt-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Ask about local laws, ordinances, or regulations..."
            className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400"
            disabled={loading}
          />
          <button
            onClick={() => handleSubmit()}
            disabled={loading || !input.trim()}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            Ask
          </button>
        </div>
        <p className="mt-2 text-center text-[10px] text-gray-400">
          CivicLens provides information, not legal advice. Always consult an attorney for legal guidance.
        </p>
      </div>
    </div>
  );
}
