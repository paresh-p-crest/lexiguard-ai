import { useEffect, useState } from "react";
import { marked } from "marked";
import { ArrowLeft } from "lucide-react";

marked.setOptions({ gfm: true, breaks: true });

export default function Documentation() {
  const [html, setHtml] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}documentation.md`)
      .then((r) => {
        if (!r.ok) throw new Error(`Could not load doc (${r.status})`);
        return r.text();
      })
      .then((md) => setHtml(marked.parse(md)))
      .catch((e) => setError(e.message || "Failed to load documentation"));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <a
              href="/"
              className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 shrink-0"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to app
            </a>
            <span className="text-slate-300 hidden sm:inline">|</span>
            <h1 className="text-sm font-semibold text-slate-900 truncate hidden sm:block">
              Demo &amp; documentation
            </h1>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {error && (
          <p className="text-red-700 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">
            {error}
          </p>
        )}
        {!error && !html && <p className="text-slate-500 text-sm">Loading…</p>}
        {html && (
          <article
            className="lexiguard-doc"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )}
        <p className="mt-10 text-[11px] text-slate-400">
          Raw file:{" "}
          <a
            href="/documentation.md"
            className="text-indigo-600 underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            /documentation.md
          </a>
        </p>
      </main>
    </div>
  );
}
