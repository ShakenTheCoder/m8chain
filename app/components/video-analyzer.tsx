"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type Decision = { label: string; confidence: number; needs_review: boolean };
type Analysis = {
  id: string;
  status: string;
  video: { id: string; url: string; duration_seconds: number | null };
  language: { code: string | null; supported: boolean | null };
  elements: { transcript: { text: string | null }; post_description: string | null };
  observation: { views: number | null; likes: number | null; shares: number | null };
  features: { topic: Decision | null; hook_type: Decision | null; format: Decision | null; call_to_action?: Decision | null };
  classifier: { status: string };
  limitations: string[];
  description: { text: string | null; sources: string[] };
  visual: { status: string; summary?: string | null };
};
type Job = { id: string; stage: string; message: string; result: Analysis | null };

function videoId(value: string) {
  try {
    const parsed = new URL(value);
    if (!["tiktok.com", "www.tiktok.com", "m.tiktok.com"].includes(parsed.hostname)) return null;
    return parsed.pathname.match(/\/video\/(\d+)\/?$/)?.[1] || null;
  } catch { return null; }
}

function decisionText(kind: string, decision: Decision | null | undefined) {
  if (!decision || decision.needs_review || decision.label === "unknown") return null;
  const label = decision.label.replaceAll("_", " ");
  if (kind === "topic") return label === "other" ? null : `The video is about ${label}.`;
  if (kind === "format") {
    const formats: Record<string, string> = {
      tutorial: "It teaches the viewer how to do something.",
      review: "It evaluates or compares a product or service.",
      testimonial: "It shares a personal experience with a product or service.",
      story: "It tells a story or describes an experience.",
    };
    return formats[decision.label] || null;
  }
  if (kind === "hook") {
    const hooks: Record<string, string> = {
      question: "It opens with a question for the viewer.",
      problem_solution: "The opening introduces a problem and offers help.",
      claim: "It opens with an assertion or a surprising fact.",
      story: "The opening starts with a personal story or event.",
    };
    return hooks[decision.label] || null;
  }
  const actions: Record<string, string> = {
    engage: "It asks viewers to like, save, share, or comment.",
    follow: "It asks viewers to follow or subscribe.",
    visit: "It asks viewers to open a link, website, or profile.",
    purchase: "It asks viewers to buy, book, or order.",
    none: "There is no explicit request for viewers to take action.",
  };
  return actions[decision.label] || null;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/organ/${path}`, { ...init, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg || "Check the TikTok URL." : "The request failed.");
  }
  return data;
}

export default function VideoAnalyzer({ analysisId }: { analysisId?: string }) {
  const [url, setUrl] = useState("");
  const [submittedUrl, setSubmittedUrl] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [loadingSaved, setLoadingSaved] = useState(!!analysisId);
  const [reused, setReused] = useState(false);
  const mounted = useRef(true);
  const activeRequest = useRef(0);
  const json = result ? JSON.stringify(result, null, 2) : "";

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;
    if (analysisId) {
      setLoadingSaved(true);
      requestJson<Analysis>(`analyses/${encodeURIComponent(analysisId)}`).then(saved => {
        if (cancelled) return;
        setResult(saved); setSubmittedUrl(saved.video.url); setReused(true);
      }).catch(cause => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Saved analysis could not be loaded.");
      }).finally(() => { if (!cancelled) setLoadingSaved(false); });
    }
    return () => { cancelled = true; mounted.current = false; activeRequest.current += 1; };
  }, [analysisId]);

  async function analyze(event: FormEvent) {
    event.preventDefault();
    const requestId = ++activeRequest.current;
    setSubmittedUrl(url.trim());
    setBusy(true); setError(""); setResult(null); setCopied(false); setReused(false);
    setJob({ id: "", stage: "queued", message: "Starting your analysis…", result: null });
    try {
      const created = await requestJson<{ id: string | null; result?: Analysis; cached: boolean }>("analyses", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }),
      });
      if (created.cached && created.result) {
        setResult(created.result); setReused(true); setJob(null); return;
      }
      const deadline = Date.now() + 20 * 60 * 1000;
      let failures = 0;
      while (mounted.current && requestId === activeRequest.current) {
        if (Date.now() > deadline) throw new Error("The analysis is taking longer than expected. Check the Python service before starting another run.");
        let current: Job;
        try {
          current = await requestJson<Job>(`jobs/${created.id}`);
          failures = 0;
        } catch (pollError) {
          failures += 1;
          if (failures >= 3) throw pollError;
          await new Promise(resolve => setTimeout(resolve, 2000));
          continue;
        }
        if (!mounted.current || requestId !== activeRequest.current) return;
        setJob(current);
        if (current.stage === "failed") throw new Error(current.message);
        if (current.stage === "complete" && current.result) {
          setResult(current.result); break;
        }
        await new Promise(resolve => setTimeout(resolve, 1500));
      }
    } catch (cause) {
      if (mounted.current && requestId === activeRequest.current) setError(cause instanceof Error ? cause.message : "Analysis failed.");
    } finally {
      if (mounted.current && requestId === activeRequest.current) setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(json); setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch { setError("Clipboard access is unavailable. Use Download JSON instead."); }
  }

  function download() {
    const objectUrl = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = objectUrl; anchor.download = `${result?.video.id}-m8chain.json`;
    anchor.click(); setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  const language = result?.language.code === "en" ? "English" : result?.language.code === "ro" ? "Romanian" : result?.language.code || "Unknown";
  const sourceUrl = result?.video.url || submittedUrl;
  const playerId = videoId(sourceUrl);
  const interpretation = result ? [
    decisionText("topic", result.features.topic),
    decisionText("format", result.features.format),
    decisionText("hook", result.features.hook_type),
    decisionText("action", result.features.call_to_action),
  ].filter(Boolean).join(" ") : "";
  const number = (value: number | null) => value === null ? "Unavailable" : new Intl.NumberFormat("en").format(value);

  return <>
    <header className="navbar">
      <nav aria-label="Main navigation"><a className="brand" href="/">m8chain</a><div className="nav-results"><a href="/graph">Graph</a><a href="/trends">Trends</a><a href="/results_db">Saved results</a></div></nav>
    </header>
    <main id="main-content">
      <section className="page-intro" aria-labelledby="page-title">
        <h1 id="page-title">{analysisId ? "Saved video analysis" : "Describing the video content"}</h1>
        {analysisId && <p className="saved-intro"><a href="/results_db">← All saved results</a><span>Loaded from the database. No new analysis is run.</span></p>}
      </section>

      {!analysisId && <form onSubmit={analyze} className="link-form">
        <label htmlFor="video-url">Video link</label>
        <div className="input-row">
          <input id="video-url" type="url" inputMode="url" required placeholder="Paste a TikTok link…" value={url} onChange={event => setUrl(event.target.value)} disabled={busy} autoComplete="off" aria-describedby="link-help" />
          <button className="primary-button" disabled={busy} type="submit">{busy ? "Analyzing…" : "Analyze"}<span aria-hidden="true"> →</span></button>
        </div>
        <div className="input-notes"><p id="link-help">Public TikTok videos · up to 2 minutes · English & Romanian</p></div>
        <p className="caption timing-note">Allow roughly 30 seconds to 2 minutes for a new video; model downloads or queueing can take longer. Saved videos load without reanalysis.</p>
      </form>}
      {error && <p className="error" role="alert">{error}</p>}
      {loadingSaved && <p className="progress" role="status"><span className="spinner" aria-hidden="true" />Loading saved analysis…</p>}
      {busy && <p className="progress" role="status"><span className="spinner" aria-hidden="true" />{job?.message || "Starting your analysis…"}</p>}
      {result && !busy && <p className="caption saved-result-link">{reused ? "Loaded the existing analysis. " : "Analysis saved. "}<a href={`/results_db/${result.id}`}>View webpage ↗</a></p>}

      {submittedUrl && <>
      <section className="document-section" aria-labelledby="video-title">
        <div className="section-heading"><h2 id="video-title">Video</h2>{sourceUrl && <a className="source-link" href={sourceUrl} target="_blank" rel="noreferrer">Open on TikTok ↗</a>}</div>
        {playerId ? <>
          <div className="player-wrap"><iframe key={playerId} src={`https://www.tiktok.com/player/v1/${playerId}?autoplay=0`} title="TikTok video player" allow="fullscreen; encrypted-media; picture-in-picture" allowFullScreen /></div>
          <p className="caption">Video won’t play? <a href={sourceUrl} target="_blank" rel="noreferrer">Watch it on TikTok ↗</a></p>
        </> : <div className="video-placeholder"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" /><path d="m10 8 6 4-6 4z" /></svg><p>Open this short link on TikTok to watch the video. The player appears when its full link is available.</p></div>}
      </section>

      <section className="document-section interpretation" aria-labelledby="interpretation-title" aria-busy={busy}>
        <div className="section-heading"><h2 id="interpretation-title">Interpretation</h2></div>
        {result && !busy ? <>
          {result.status !== "complete" && <p className="result-note">{result.status === "unsupported_language" ? "This video’s language isn’t supported yet. Available details are shown below." : "Some parts of this video couldn’t be analyzed. Here’s what is available."}</p>}
          <p className="reading-text">{result.visual.summary || result.description.text || "A description isn’t available for this video."}</p>
          {interpretation && <p className="reading-text">{interpretation}</p>}
          {!interpretation && <p className="caption">There isn’t enough analysis to explain the topic, opening, or format reliably.</p>}
          <dl className="video-facts"><div><dt>Language</dt><dd>{language}</dd></div><div><dt>Length</dt><dd>{result.video.duration_seconds === null ? "Unavailable" : `${result.video.duration_seconds} seconds`}</dd></div><div><dt>Views</dt><dd>{number(result.observation.views)}</dd></div><div><dt>Likes</dt><dd>{number(result.observation.likes)}</dd></div><div><dt>Shares</dt><dd>{number(result.observation.shares)}</dd></div></dl>
          {result.elements.post_description && <div className="text-section"><h3>Post caption</h3><p>{result.elements.post_description}</p></div>}
          {result.elements.transcript.text && <div className="text-section"><h3>What’s said</h3><blockquote>{result.elements.transcript.text}</blockquote></div>}
          <p className="caption analysis-note">AI interpretations may miss context. Visual descriptions use sampled frames; spoken text is kept in its original language.</p>
        </> : <p className="empty-text">{busy ? "Reading the video. Your interpretation will appear here when it’s ready." : "A plain-language explanation of what happens, what’s said, and how the video is presented."}</p>}
      </section>

      <details className="json-disclosure" key={result?.id || "empty"}>
        <summary>Show JSON schema</summary>
        <div className="json-content"><p className="caption">{result ? "The full structured analysis for this video." : "The structured output will appear when the analysis is ready."} <a href="/api/organ/schema" target="_blank" rel="noreferrer">View schema definition ↗</a></p>
          {result && <><div className="json-actions"><button onClick={copy}>{copied ? "Copied" : "Copy JSON"}</button><button onClick={download}>Download JSON ↓</button></div><pre tabIndex={0} aria-label="Video analysis JSON"><code>{json}</code></pre></>}
        </div>
      </details>
      <footer className="page-footer">m8chain<span>A closer look at a video.</span></footer>
      </>}
    </main>
  </>;
}
