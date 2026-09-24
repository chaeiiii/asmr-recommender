"use client";

import { useEffect, useState } from "react";

export default function Page() {
  const [status, setStatus] = useState("Checking backend health…");

  useEffect(() => {
    const controller = new AbortController();
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

    async function checkHealth() {
      try {
        const response = await fetch(`${baseUrl.replace(/\/$/, "")}/health`, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Health request failed");
        const data: unknown = await response.json();
        if (!data || typeof data !== "object" || !("status" in data) || data.status !== "ok") {
          throw new Error("Unexpected health response");
        }
        setStatus("Backend is healthy.");
      } catch {
        if (!controller.signal.aborted) {
          setStatus("Backend unavailable. Check that the API server is running.");
        }
      }
    }

    void checkHealth();
    return () => controller.abort();
  }, []);

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-semibold">ASMR Recommender</h1>
      <p className="mt-4 text-slate-600">Development bootstrap</p>
      <p role="status" className="mt-6 rounded-lg border border-slate-200 bg-white p-4">
        {status}
      </p>
    </main>
  );
}
