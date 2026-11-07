"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Video = { id: string; video_id: string; url: string; label: string; description: string | null; creator_id: string | null; connection_count: number };
type Evidence = { signal: string; value: string; similarity: number; strength: string; lexical_similarity?: number | null; semantic_similarity?: number | null; basis?: string };
type Connection = { id: string; source: string; target: string; strength: string; score: number; evidence: Evidence[] };
type Graph = { revision: number; updated_at: string; nodes: Video[]; edges: Connection[]; limitations: string[] };
type Point = { x: number; y: number };
const names: Record<string, string> = { sound: "Sound", script: "Script", subtitles: "On-screen text", caption: "Caption", visual: "Visual elements" };

// Keep directly connected clips nearby without a force simulation collapsing
// dense components onto the map boundaries. Every clip gets its own grid cell.
function layout(nodes: Video[], edges: Connection[]): Record<string, Point> {
  const neighbors = new Map(nodes.map(node => [node.id, [] as string[]]));
  for (const edge of edges) {
    neighbors.get(edge.source)?.push(edge.target);
    neighbors.get(edge.target)?.push(edge.source);
  }
  const visited = new Set<string>();
  const ordered: string[] = [];
  for (const node of nodes) {
    if (visited.has(node.id)) continue;
    const queue = [node.id];
    visited.add(node.id);
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i];
      ordered.push(id);
      for (const neighbor of neighbors.get(id) || []) {
        if (!visited.has(neighbor)) { visited.add(neighbor); queue.push(neighbor); }
      }
    }
  }
  const columns = Math.max(1, Math.ceil(Math.sqrt(nodes.length * 1.6)));
  const rows = Math.max(1, Math.ceil(nodes.length / columns));
  return Object.fromEntries(ordered.map((id, index) => [id, {
    x: 70 + (index % columns + .5) * 860 / columns,
    y: 100 + (Math.floor(index / columns) + .5) * 430 / rows,
  }]));
}

export default function VideoGraph() {
  const [data, setData] = useState<Graph | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [signal, setSignal] = useState("all");
  const [strongOnly, setStrongOnly] = useState(true);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<{ kind: "node" | "edge"; id: string } | null>(null);
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 });
  const svg = useRef<SVGSVGElement>(null);
  const [mapSize, setMapSize] = useState({ width: 900, height: 550 });
  const drag = useRef<{ id: string | null; x: number; y: number; origin: Point } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const response = await fetch("/api/organ/graph", { cache: "no-store", signal: controller.signal });
        const body = await response.json();
        if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Video connections could not be loaded.");
        if (!controller.signal.aborted) { setData(previous => previous && previous.revision === body.revision && previous.updated_at === body.updated_at ? previous : body); setError(""); }
      } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Video connections could not be loaded."); }
      finally { if (!controller.signal.aborted) timer = setTimeout(load, 3000); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);
  useEffect(() => {
    const element = svg.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      const box = element.getBoundingClientRect();
      if (box.width && box.height) setMapSize({ width: box.width, height: box.height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [data?.nodes.length]);
  const nodes = data?.nodes || [];
  const byId = useMemo(() => new Map(data?.nodes.map(n => [n.id, n])), [data]);
  const edges = useMemo(() => data?.edges.filter(e => (!strongOnly || e.strength === "strong") && (signal === "all" || e.evidence.some(item => item.signal === signal))) || [], [data, signal, strongOnly]);
  useEffect(() => {
    if (data) setPositions(layout(data.nodes, edges));
  }, [data, edges]);
  const node = selected?.kind === "node" ? byId.get(selected.id) : null;
  const edge = selected?.kind === "edge" ? edges.find(e => e.id === selected.id) : null;
  const related = node ? edges.filter(e => e.source === node.id || e.target === node.id) : [];
  const activeIds = new Set(node ? [node.id, ...related.flatMap(e => [e.source, e.target])] : edge ? [edge.source, edge.target] : []);
  function changeZoom(next: number) {
    next = Math.max(.6, Math.min(3, next));
    setPan(p => ({ x: p.x + 500 / zoom - 500 / next, y: p.y + 300 / zoom - 300 / next })); setZoom(next);
  }
  function reset() { setZoom(1); setPan({ x: 0, y: 0 }); if (data) setPositions(layout(data.nodes, edges)); }
  function choose(id: string) { setSelected({ kind: "node", id }); }
  function videoLink(video: Video | undefined) {
    return video ? <div className="graph-clip"><a href={`/results_db/${video.id}`}>{video.label}</a><p className="caption">{video.creator_id || "Creator unavailable"}</p><a className="caption" href={video.url} target="_blank" rel="noreferrer">Watch on TikTok ↗</a></div> : null;
  }
  return <>
    <header className="navbar"><nav aria-label="Main navigation"><a className="brand" href="/">m8chain</a><div className="nav-results"><a href="/trends">Trends</a><a href="/results_db">Saved videos</a></div></nav></header>
    <main className="graph-page"><section className="page-intro"><h1>Video connections</h1><p className="results-intro">Every clip is a starting point. Explore the sounds, words, and visual elements that connect them.</p></section>
      <div className="results-toolbar"><p className="caption" role="status">{data ? `${nodes.length} videos · ${edges.length} visible connections` : error ? "Connections unavailable" : "Loading your videos…"}</p><button className="secondary-button" onClick={() => setRefresh(v => v + 1)}>Refresh</button></div>
      <p className="caption graph-update">Updates after each newly saved video. Trends require strong evidence for the same recurring element.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {data && nodes.length === 0 && <div className="results-empty"><h2>Add your first video</h2><p>Every analyzed video appears here, even before it has a connection.</p><a className="primary-link" href="/">Analyze a video →</a></div>}
      {data && nodes.length > 0 && <>
        <div className="graph-filters"><label>Find a video<input type="search" value={search} placeholder="Search caption or video ID" onChange={e => setSearch(e.target.value)} /></label><label>Connection<select value={signal} onChange={e => { setSignal(e.target.value); setSelected(null); }}><option value="all">All shared elements</option>{Object.entries(names).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label><label className="graph-checkbox"><input type="checkbox" checked={strongOnly} onChange={e => { setStrongOnly(e.target.checked); setSelected(null); }} />Strong matches only</label></div>
        <div className="graph-workspace"><div className="graph-map-column">
          <div className="graph-map"><div className="graph-zoom"><button aria-label="Zoom out" onClick={() => changeZoom(zoom - .2)}>−</button><button aria-label="Zoom in" onClick={() => changeZoom(zoom + .2)}>+</button><button onClick={reset}>Reset view</button></div>
            <svg ref={svg} viewBox={`${pan.x} ${pan.y} ${1000 / zoom} ${600 / zoom}`} role="group" aria-label="Video relationship map. Select a video or connection to inspect its evidence." onPointerDown={e => {
              if (e.target === e.currentTarget) { drag.current = { id: null, x: e.clientX, y: e.clientY, origin: pan }; e.currentTarget.setPointerCapture(e.pointerId); }
            }} onPointerMove={e => {
              const current = drag.current, box = svg.current?.getBoundingClientRect();
              if (!current || !box) return;
              // preserveAspectRatio is disabled so these coordinate ratios stay exact.
              const dx = (e.clientX - current.x) * 1000 / box.width / zoom, dy = (e.clientY - current.y) * 600 / box.height / zoom;
              if (current.id) setPositions(previous => ({ ...previous, [current.id!]: { x: current.origin.x + dx, y: current.origin.y + dy } }));
              else setPan({ x: current.origin.x - dx, y: current.origin.y - dy });
            }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} preserveAspectRatio="none">
              {edges.map(item => { const a = positions[item.source], b = positions[item.target]; if (!a || !b) return null; const active = item.id === edge?.id || node && (item.source === node.id || item.target === node.id); return <g key={item.id} className={`graph-edge ${active ? "is-active" : ""}`} role="button" tabIndex={0} aria-label={`${byId.get(item.source)?.label} and ${byId.get(item.target)?.label}: ${item.strength} ${[...new Set(item.evidence.map(e => names[e.signal]))].join(", ")} connection`} onClick={() => setSelected({ kind: "edge", id: item.id })} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected({ kind: "edge", id: item.id }); } }}><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth="22" /><line className="graph-edge-line" x1={a.x} y1={a.y} x2={b.x} y2={b.y} strokeDasharray={item.strength === "weak" ? "6 6" : undefined} strokeWidth={item.strength === "strong" ? 2 + item.score * 3 : 1.5} /></g>; })}
              {nodes.map((item, index) => { const p = positions[item.id]; if (!p) return null; const matches = !search || `${item.label} ${item.video_id}`.toLowerCase().includes(search.toLowerCase()); const dimmed = !matches || activeIds.size > 0 && !activeIds.has(item.id); return <g key={item.id} transform={`translate(${p.x},${p.y}) scale(${1000 / mapSize.width},${600 / mapSize.height})`} className={`graph-node ${selected?.id === item.id ? "is-selected" : ""} ${dimmed ? "is-dimmed" : ""}`} tabIndex={0} role="button" aria-label={`Video ${index + 1}: ${item.label}. ${item.connection_count} connections.`} onClick={() => choose(item.id)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(item.id); } }} onPointerDown={e => { e.stopPropagation(); choose(item.id); drag.current = { id: item.id, x: e.clientX, y: e.clientY, origin: p }; e.currentTarget.setPointerCapture(e.pointerId); }}><title>{item.label}</title><circle r={node?.id === item.id ? 25 : 21} /><text textAnchor="middle" dy="5" className="graph-node-number">{index + 1}</text></g>; })}
            </svg>
          </div>
          <div className="graph-legend"><span>— Strong match</span><span>┄ Weaker similarity</span><span>Drag a node or pan the map · use + / − to zoom</span></div>
          {edges.length === 0 && <p className="result-note">{data.edges.length ? "No connections match these filters. All videos remain visible." : "No shared elements have been detected yet. Your videos are still shown; add another clip or inspect each analysis for missing information."}</p>}
        </div>
        <aside className="graph-inspector" aria-label="Connection details" aria-live="polite">
          {node ? <><div className="section-heading"><h2>Video {nodes.indexOf(node) + 1}</h2><button className="text-link-button" onClick={() => setSelected(null)}>Clear</button></div>{videoLink(node)}{node.description && <p className="graph-description">{node.description}</p>}<h3>{related.length} visible {related.length === 1 ? "connection" : "connections"}</h3>{related.map(item => <button className="graph-connection-button" key={item.id} onClick={() => setSelected({ kind: "edge", id: item.id })}><span>{byId.get(item.source === node.id ? item.target : item.source)?.label}</span><small>{item.strength === "strong" ? "Strong match" : "Weaker similarity"} · {[...new Set(item.evidence.map(e => names[e.signal]))].join(", ")}</small></button>)}{related.length === 0 && <p className="caption">No visible connections for this clip. This doesn’t establish that it is unique; some elements may be missing from its analysis.</p>}</> : edge ? <><div className="section-heading"><h2>{edge.strength === "strong" ? "Strong match" : "Weaker similarity"}</h2><button className="text-link-button" onClick={() => setSelected(null)}>Clear</button></div>{videoLink(byId.get(edge.source))}{videoLink(byId.get(edge.target))}<h3>Why they connect</h3>{edge.evidence.map((item, i) => <div className="graph-evidence" key={i}><strong>{names[item.signal]}</strong><p>{item.value}</p><span className="caption">{item.strength === "strong" ? "Matching evidence" : "Weaker similarity"} · {item.signal === "sound" ? "Exact sound ID" : `${(item.similarity * 100).toFixed(1)}% combined similarity`}</span>{item.lexical_similarity != null && item.semantic_similarity != null && <p className="caption">Wording: {(item.lexical_similarity * 100).toFixed(1)}% · Meaning: {(item.semantic_similarity * 100).toFixed(1)}% · Combined 50/50.</p>}</div>)}{edge.strength === "weak" && <p className="caption">Wording and meaning similarity suggest a relationship. Review the original clips for context; this is candidate evidence.</p>}</> : <><h2>Follow a connection</h2><p>Select a video to explore its neighbors, or a line to see exactly what two clips share.</p><p className="caption">Thicker solid lines carry stronger weighted evidence. Sound has the greatest weight. Uncheck “Strong matches only” to inspect weaker similarities. Weak connections do not establish trends.</p></>}
        </aside></div>
        <details className="guide-details"><summary>All videos & accessible list</summary><ul className="graph-video-list">{nodes.filter(n => !search || `${n.label} ${n.video_id}`.toLowerCase().includes(search.toLowerCase())).map(n => <li key={n.id}><button className="text-link-button" onClick={() => choose(n.id)}>{n.label}</button><span className="caption">{n.connection_count} connections</span></li>)}</ul></details>
        <details className="guide-details"><summary>How to read this map</summary><ul>{data.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul><p>The map shows all saved videos, including isolated clips. Proximity helps arrange the map; the lines and their evidence explain the actual relationships.</p></details>
      </>}
      <footer className="page-footer">m8chain<span>Every relationship starts somewhere.</span></footer>
    </main>
  </>;
}
