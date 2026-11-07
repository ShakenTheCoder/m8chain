"use client";

import { useEffect, useState } from "react";

type Signal = "sound" | "script" | "subtitles" | "caption" | "visual";
type Trend = {
  id: string; title: string; classification: string; status: string; matching_score: number; creator_count: number;
  clips: { analysis_id: string; video_id: string; url: string; caption: string | null; creator_id: string | null }[];
  evidence: { signal: Signal; value: string; clip_ids: string[]; similarity: number; strength: string; lexical_similarity?: number | null; semantic_similarity?: number | null; basis?: string }[];
  execution_guide: { specific_to_trend: string[]; steps: string[]; can_adapt: string[]; review_before_posting: string[] };
  limitations: string[];
};
type Results = {
  revision: number; updated_at: string;
  trends: Trend[]; total_saved_videos: number; analyzed_videos: number; grouped_videos: number; ungrouped_videos: number;
  truncated: boolean; scan_limit: number; signal_weights: Record<Signal, number>;
};
const labels: Record<string, string> = { sound: "Sound", script: "Script", subtitles: "On-screen text", caption: "Caption", visual: "Visual elements", mixed: "Multiple shared elements" };

function TrendRecord({ trend }: { trend: Trend }) {
  const [message, setMessage] = useState("");
  const json = JSON.stringify(trend, null, 2);
  async function copy() {
    try { await navigator.clipboard.writeText(json); setMessage("JSON copied."); }
    catch { setMessage("Couldn’t copy. Use Download JSON instead."); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${trend.id}.json`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <article className="trend-record" id={trend.id}>
    <div className="trend-meta"><span>Candidate · {labels[trend.classification]}</span><span>{trend.clips.length} clips · {trend.creator_count} known {trend.creator_count === 1 ? "creator" : "creators"}</span></div>
    <h2>{trend.title}</h2>
    <section className="trend-section" aria-label="Shared elements"><h3>What makes this a pattern</h3><ul className="evidence-list">{trend.evidence.map((item, i) => <li key={i}><span className="evidence-label">{labels[item.signal]}</span><p>{item.value}</p><span className="caption">{item.strength === "weak" ? "Weaker similarity" : "Matching evidence"} · {item.clip_ids.length} clips · <a href={`#${trend.id}-clips`}>see source clips below</a></span>{item.lexical_similarity != null && item.semantic_similarity != null && <p className="caption">Wording: {(item.lexical_similarity * 100).toFixed(1)}% · Meaning: {(item.semantic_similarity * 100).toFixed(1)}% · Combined: {(item.similarity * 100).toFixed(1)}% (50/50)</p>}</li>)}</ul></section>
    <section className="trend-section" aria-label="Execution guide"><h3>How to execute this trend</h3><ol className="guide-steps">{trend.execution_guide.steps.map((step, i) => <li key={i}>{step}</li>)}</ol>
      <details className="guide-details"><summary>What to preserve & what you can adapt</summary><h4>Keep recognizable</h4><ul>{trend.execution_guide.specific_to_trend.map((item, i) => <li key={i}>{item}</li>)}</ul><h4>Make it yours</h4><ul>{trend.execution_guide.can_adapt.map((item, i) => <li key={i}>{item}</li>)}</ul></details>
      <p className="caption">Suggested from the saved evidence. Review the full clips for exact wording, pacing, and context.</p>
    </section>
    <section className="trend-section" id={`${trend.id}-clips`} aria-label="Clips in this trend"><h3>Clips in this trend</h3><ul className="trend-clips">{trend.clips.map(clip => <li key={clip.analysis_id}><div><a href={`/results_db/${clip.analysis_id}`}>{clip.caption || `Video ${clip.video_id}`}</a><p className="caption">{clip.creator_id || "Creator unavailable"} · {clip.video_id}</p><p className="caption">Matches: {[...new Set(trend.evidence.filter(e => e.clip_ids.includes(clip.analysis_id)).map(e => labels[e.signal]))].join(", ")}</p></div><a className="clip-original" href={clip.url} target="_blank" rel="noreferrer">TikTok ↗</a></li>)}</ul></section>
    <details className="guide-details"><summary>Evidence limits</summary><ul>{trend.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul><p className="caption">Weighted match score: {trend.matching_score.toFixed(3)}. This measures matching evidence, not the probability of success or virality.</p></details>
    <details className="json-disclosure"><summary>Show trend JSON</summary><div className="json-content"><div className="json-actions"><button onClick={copy}>Copy JSON</button><button onClick={download}>Download JSON ↓</button></div><p className="caption" role="status">{message}</p><pre tabIndex={0} aria-label={`JSON for ${trend.title}`}><code>{json}</code></pre></div></details>
  </article>;
}

export default function TrendsPage() {
  const [data, setData] = useState<Results | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [filter, setFilter] = useState("all");
  const [visibleCount, setVisibleCount] = useState(12);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const response = await fetch("/api/organ/trends", { cache: "no-store", signal: controller.signal });
        const body = await response.json();
        if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Trends could not be loaded.");
        if (!controller.signal.aborted) {
          const result = body as Results;
          setData(previous => previous?.revision === result.revision && previous.updated_at === result.updated_at ? previous : result);
          setError("");
        }
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Trends could not be loaded.");
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          timer = setTimeout(load, 3000);
        }
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);
  const trends = data?.trends.filter(t => filter === "all" || t.evidence.some(e => e.signal === filter)) || [];
  return <>
    <header className="navbar"><nav aria-label="Main navigation"><a className="brand" href="/">m8chain</a><div className="nav-results"><a href="/graph">Graph</a><a href="/results_db">Saved videos</a><a href="/">Analyze a video</a></div></nav></header>
    <main className="trends-page"><section className="page-intro"><h1>Trends</h1><p className="results-intro">The sounds, words, and visual ideas your saved videos have in common.</p></section>
      <div className="results-toolbar"><p className="caption" role="status">{loading ? "Comparing saved videos…" : data ? `${data.trends.length} candidate ${data.trends.length === 1 ? "trend" : "trends"} · ${data.grouped_videos} of ${data.analyzed_videos} videos grouped` : "Your saved video patterns"}</p><button className="secondary-button" onClick={() => setRefresh(n => n + 1)} disabled={loading}>Refresh</button></div>
      <p className="caption">Updates automatically after each newly saved video.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {!error && data && <>
        <details className="guide-details method-details"><summary>How trends are grouped</summary><p>Only strong matching evidence creates a candidate trend. Groups follow a specific shared cue, and every pair in a group must support that cue. Groups may overlap; a bridge between different cues does not merge them into one large trend. Weak graph connections do not establish trend membership. Sound is the strongest signal. Text comparisons combine 50% word overlap and 50% meaning similarity.</p><ul>{Object.entries(data.signal_weights).map(([key, weight]) => <li key={key}>{labels[key]}: {(weight * 100).toFixed(2)}% weight</li>)}</ul><p>Repeated content is a candidate pattern. Growth over time and wider adoption haven’t been established. Each evidence item identifies the clips that support it. A connection through another video is not a direct match.</p><a href="/api/organ/trends/schema" target="_blank" rel="noreferrer">View trend JSON schema ↗</a></details>
        {data.truncated && <p className="result-note">Showing patterns from the latest {data.scan_limit} of {data.total_saved_videos} saved videos.</p>}
        {data.trends.length > 0 && <div className="trend-filter"><label htmlFor="trend-filter">Shared element</label><select id="trend-filter" value={filter} onChange={event => { setFilter(event.target.value); setVisibleCount(12); }}><option value="all">All elements</option>{Object.entries(labels).filter(([key]) => key !== "mixed").map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></div>}
        {!loading && data.trends.length === 0 && <div className="results-empty"><h2>{data.analyzed_videos < 2 ? "Add more videos to find a pattern" : "No shared patterns found yet"}</h2><p>{data.analyzed_videos < 2 ? "Analyze at least two different TikTok videos. Trends will appear when their saved analyses share recognizable elements." : "These videos don’t have enough matching evidence. Add clips with shared sounds, captions, scripts, on-screen text, or visual ideas."}</p><a className="primary-link" href="/">Analyze a video →</a></div>}
        {!loading && data.trends.length > 0 && trends.length === 0 && <p className="results-empty">No trends match this element. Choose another filter.</p>}
        <div aria-busy={loading}>{trends.slice(0, visibleCount).map(trend => <TrendRecord key={trend.id} trend={trend} />)}</div>
        {trends.length > visibleCount && <button className="secondary-button" onClick={() => setVisibleCount(count => count + 12)}>Show {Math.min(12, trends.length - visibleCount)} more trends</button>}
        {data.ungrouped_videos > 0 && <p className="caption">{data.ungrouped_videos} saved {data.ungrouped_videos === 1 ? "video has" : "videos have"} no qualifying match yet.</p>}
      </>}
      <footer className="page-footer">m8chain<span>Patterns, with their evidence.</span></footer>
    </main>
  </>;
}
