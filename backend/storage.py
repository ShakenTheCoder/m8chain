"""One saved analysis per TikTok video, with URL aliases and legacy-link redirects."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import re
import sqlite3

from .models import Analysis, AnalyzeRequest
from .trends import METHOD, extract_trends
from .video_graph import GRAPH_METHOD, extract_graph


def video_id_from_url(url: str) -> str | None:
    match = re.search(r"/video/(\d+)(?:/)?$", url)
    return match.group(1) if match else None


def normalized_url(value: str) -> str | None:
    try:
        return AnalyzeRequest(url=value).url
    except ValueError:
        return None


class AnalysisStore:
    def __init__(self, path: Path):
        self.path = path

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path, timeout=15)

    def initialize(self):
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, video_id TEXT, created_at TEXT, result TEXT, raw TEXT)")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(analyses)")}
            if "processing_seconds" not in columns:
                connection.execute("ALTER TABLE analyses ADD COLUMN processing_seconds REAL")
            connection.execute("CREATE TABLE IF NOT EXISTS analysis_urls (url TEXT PRIMARY KEY, analysis_id TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS analysis_redirects (old_id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL)")
            duplicates = connection.execute("SELECT video_id FROM analyses GROUP BY video_id HAVING count(*)>1").fetchall()
        if duplicates:
            # Back up committed data before consolidating legacy duplicates; keep their media.
            backup = self.path.with_name("organ-before-dedup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".sqlite3")
            with self.connect() as source, sqlite3.connect(backup) as destination:
                source.backup(destination)
        with self.connect() as connection:
            for (video_id,) in duplicates:
                rows = connection.execute("SELECT id, created_at, result FROM analyses WHERE video_id=?", (video_id,)).fetchall()

                def quality(row):
                    data = json.loads(row[2])
                    return (data.get("status") == "complete", data.get("visual", {}).get("status") == "complete",
                            bool(data.get("elements", {}).get("transcript", {}).get("text")),
                            data.get("classifier", {}).get("status") == "complete", row[1])

                winner = max(rows, key=quality)[0]
                for old_id, _, encoded in rows:
                    self._remember_urls(connection, winner, json.loads(encoded))
                    if old_id != winner:
                        connection.execute("UPDATE analysis_urls SET analysis_id=? WHERE analysis_id=?", (winner, old_id))
                        connection.execute("UPDATE analysis_redirects SET analysis_id=? WHERE analysis_id=?", (winner, old_id))
                        connection.execute("INSERT OR REPLACE INTO analysis_redirects VALUES (?, ?)", (old_id, winner))
                        connection.execute("DELETE FROM analyses WHERE id=?", (old_id,))
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS analyses_video_unique ON analyses(video_id)")
            for analysis_id, encoded in connection.execute("SELECT id, result FROM analyses").fetchall():
                self._remember_urls(connection, analysis_id, json.loads(encoded))
            connection.execute("CREATE TABLE IF NOT EXISTS trend_state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, computed_revision INTEGER NOT NULL, result TEXT)")
            connection.execute("INSERT OR IGNORE INTO trend_state VALUES (1, (SELECT count(*) FROM analyses), -1, NULL)")
            connection.execute("CREATE TRIGGER IF NOT EXISTS trends_after_video_insert AFTER INSERT ON analyses BEGIN UPDATE trend_state SET revision=revision+1 WHERE id=1; END")
            if duplicates:
                connection.execute("UPDATE trend_state SET revision=revision+1 WHERE id=1")

    @staticmethod
    def _remember_urls(connection, analysis_id: str, result: dict, submitted_url: str | None = None):
        urls = [submitted_url, result.get("video", {}).get("url")]
        urls.extend(result.get("collection", {}).get("discovery_queries", []))
        for value in urls:
            url = normalized_url(value) if isinstance(value, str) else None
            if url:
                connection.execute("INSERT OR REPLACE INTO analysis_urls VALUES (?, ?)", (url, analysis_id))

    def get(self, analysis_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT result FROM analyses WHERE id=?", (analysis_id,)).fetchone()
            if row is None:
                row = connection.execute("SELECT a.result FROM analyses a JOIN analysis_redirects r ON r.analysis_id=a.id WHERE r.old_id=?", (analysis_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def find(self, url: str) -> dict | None:
        video_id = video_id_from_url(url)
        with self.connect() as connection:
            row = connection.execute("SELECT a.result FROM analyses a JOIN analysis_urls u ON u.analysis_id=a.id WHERE u.url=?", (url,)).fetchone()
            if row is None and video_id:
                row = connection.execute("SELECT result FROM analyses WHERE video_id=?", (video_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def save(self, result: Analysis, raw: dict, submitted_url: str, processing_seconds: float) -> dict:
        with self.connect() as connection:
            inserted = connection.execute(
                "INSERT OR IGNORE INTO analyses (id, video_id, created_at, result, raw, processing_seconds) VALUES (?, ?, ?, ?, ?, ?)",
                (result.id, result.video.id, datetime.now(timezone.utc).isoformat(), result.model_dump_json(),
                 json.dumps(raw, ensure_ascii=False), round(processing_seconds, 2)),
            ).rowcount == 1
            row = connection.execute("SELECT id, result FROM analyses WHERE video_id=?", (result.video.id,)).fetchone()
            canonical = json.loads(row[1])
            self._remember_urls(connection, row[0], canonical, submitted_url)
            if result.id != row[0]:
                connection.execute("INSERT OR REPLACE INTO analysis_redirects VALUES (?, ?)", (result.id, row[0]))
        if inserted:
            try:
                self.trend_snapshot()
            except Exception:
                # The analysis is already committed. Leave the revision dirty so
                # the next snapshot read retries; never lose a saved video.
                logging.getLogger(__name__).exception("Trend update failed; saved analysis retained")
        return canonical

    def list(self, limit: int, offset: int) -> dict:
        with self.connect() as connection:
            total = connection.execute("SELECT count(*) FROM analyses").fetchone()[0]
            rows = connection.execute("SELECT id, created_at, result, processing_seconds FROM analyses ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        items = []
        for analysis_id, created_at, encoded, seconds in rows:
            result = json.loads(encoded)
            items.append({"id": analysis_id, "created_at": created_at, "video_id": result["video"]["id"],
                          "video_url": result["video"]["url"], "status": result["status"],
                          "caption": result.get("elements", {}).get("post_description"),
                          "description": result.get("visual", {}).get("summary") or result.get("description", {}).get("text"),
                          "language": result.get("language", {}).get("code"), "processing_seconds": seconds})
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def trend_records(self, limit: int | None = 1000) -> tuple[list[dict], int]:
        """Bound the pairwise comparison cost; use a single read snapshot."""
        with self.connect() as connection:
            connection.execute("BEGIN")
            total = connection.execute("SELECT count(*) FROM analyses").fetchone()[0]
            rows = connection.execute("SELECT result FROM analyses ORDER BY created_at DESC, id DESC LIMIT ?", (limit if limit is not None else -1,)).fetchall()
        return [json.loads(row[0]) for row in rows], total

    def trend_snapshot(self) -> dict:
        """Publish one persisted snapshot per database revision; GETs reuse it."""
        def current(connection):
            row = connection.execute("SELECT revision, computed_revision, result FROM trend_state WHERE id=1").fetchone()
            result = json.loads(row[2]) if row[2] else None
            valid = row[0] == row[1] and result is not None and result.get("method") == METHOD and result.get("graph", {}).get("method") == GRAPH_METHOD
            return row[0], result if valid else None

        with self.connect() as connection:
            revision, result = current(connection)
            if result is not None:
                return result
            # Serialize rebuilds and block concurrent inserts until publication.
            # A second caller rechecks after acquiring the lock, avoiding duplicate work.
            connection.execute("BEGIN IMMEDIATE")
            revision, result = current(connection)
            if result is not None:
                return result
            records, total = self.trend_records(limit=None)
            result = {**extract_trends(records), "total_saved_videos": total,
                      "scan_limit": None, "truncated": False, "revision": revision,
                      "updated_at": datetime.now(timezone.utc).isoformat(), "update_trigger": "new_video_saved"}
            result["graph"] = extract_graph(records)
            connection.execute("UPDATE trend_state SET computed_revision=?, result=? WHERE id=1",
                               (revision, json.dumps(result, ensure_ascii=False)))
            return result
