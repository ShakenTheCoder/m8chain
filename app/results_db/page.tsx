"use client";

import { useEffect, useState } from "react";

type Entry = {
  id: string;
  created_at: string;
  video_id: string;
  video_url: string;
  status: string;
  caption: string | null;
  description: string | null;
  language: string | null;
  processing_seconds: number | null;
};
type Results = { items: Entry[]; total: number; limit: number; offset: number };
const pageSize = 20;

export default function ResultsDatabase() {
  const [data, setData] = useState<Results | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    fetch(`/api/organ/analyses?limit=${pageSize}&offset=${offset}`, { cache: "no-store", signal: controller.signal })
      .then(async response => {
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Saved results could not be loaded.");
        return result as Results;
      }).then(result => { if (!controller.signal.aborted) setData(result); }).catch(cause => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Saved results could not be loaded.");
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [offset, refresh]);

  return <>
    <header className="navbar"><nav aria-label="Main navigation"><a className="brand" href="/">m8chain</a><div className="nav-results"><a href="/graph">Graph</a><a href="/trends">Trends</a><a href="/">Analyze a video</a></div></nav></header>
    <main className="results-page">
      <section className="page-intro"><h1>Analyzed clips (DB)</h1></section>
      <div className="results-toolbar"><p className="caption" aria-live="polite">{data ? `${data.total} saved ${data.total === 1 ? "video" : "videos"}` : "Your analysis library"}{loading ? " · Loading…" : ""}</p><button className="secondary-button" onClick={() => setRefresh(value => value + 1)} disabled={loading}>Refresh</button></div>
      {error && <p className="error" role="alert">{error}</p>}
      {!loading && !error && data?.total === 0 && <div className="results-empty"><h2>No saved analyses yet</h2><p>Analyze your first TikTok video. Its result will appear here automatically.</p><a className="primary-link" href="/">Analyze a video →</a></div>}
      <div className="results-list" aria-busy={loading}>
        {data?.items.map(entry => <article className="result-entry" key={entry.id}>
          <div className="entry-heading"><span className="entry-status">{entry.status.replaceAll("_", " ")}</span><time className="caption" dateTime={entry.created_at}>{new Date(entry.created_at).toLocaleString()}</time></div>
          <h2>{entry.caption || `TikTok video ${entry.video_id}`}</h2>
          {entry.description && <p className="entry-description">{entry.description}</p>}
          <div className="entry-actions"><a className="primary-link" href={`/results_db/${entry.id}`}>View webpage →</a><a href={`/api/organ/analyses/${entry.id}`} target="_blank" rel="noreferrer">View JSON ↗</a><a href={entry.video_url} target="_blank" rel="noreferrer">Open TikTok ↗</a></div>
        </article>)}
      </div>
      {data && data.total > pageSize && <nav className="pagination" aria-label="Results pages"><button className="secondary-button" disabled={loading || offset === 0} onClick={() => setOffset(value => Math.max(0, value - pageSize))}>← Previous</button><span className="caption">{offset + 1}–{Math.min(offset + pageSize, data.total)} of {data.total}</span><button className="secondary-button" disabled={loading || offset + pageSize >= data.total} onClick={() => setOffset(value => value + pageSize)}>Next →</button></nav>}
    </main>
  </>;
}
