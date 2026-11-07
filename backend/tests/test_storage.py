from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock
import json
import sqlite3
import uuid

from fastapi.testclient import TestClient
import pytest
from backend.models import Analysis, Classifier, Collection, Elements, Observation, Video, VisualAnalysis
from backend.storage import AnalysisStore

URL = "https://www.tiktok.com/@creator/video/123456789"


def record(video_id="123456789", visual=False):
    return Analysis(id=str(uuid.uuid4()), video=Video(id=video_id, url=URL.replace("123456789", video_id)),
                    collection=Collection(run_id="test-run", collected_at="2026-11-07T12:00:00Z", discovery_queries=["https://vm.tiktok.com/SavedShort/"]),
                    elements=Elements(post_description="Original caption"),
                    observation=Observation(observed_at="2026-11-07T12:00:00Z"),
                    visual=VisualAnalysis(status="complete", summary="A scene") if visual else VisualAnalysis(),
                    classifier=Classifier(model="test", min_confidence=.6))


def test_migration_consolidates_duplicates_keeps_best_and_backs_up_originals(tmp_path):
    path = tmp_path / "organ.sqlite3"
    best, newer = record(visual=True), record()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE analyses (id TEXT PRIMARY KEY, video_id TEXT, created_at TEXT, result TEXT, raw TEXT)")
        for item, date in [(best, "2026-11-06"), (newer, "2026-11-07")]:
            connection.execute("INSERT INTO analyses VALUES (?, ?, ?, ?, ?)", (item.id, item.video.id, date, item.model_dump_json(), '{"original":true}'))
    store = AnalysisStore(path)
    store.initialize()
    assert store.list(20, 0)["total"] == 1
    assert store.get(newer.id)["id"] == best.id
    assert store.get(best.id)["visual"]["status"] == "complete"
    assert store.find("https://m.tiktok.com/@new-name/video/123456789")["id"] == best.id
    backups = list(tmp_path.glob("organ-before-dedup-*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("SELECT count(*) FROM analyses").fetchone()[0] == 2
        assert backup.execute("SELECT raw FROM analyses LIMIT 1").fetchone()[0] == '{"original":true}'
    store.initialize()
    assert len(list(tmp_path.glob("organ-before-dedup-*.sqlite3"))) == 1


def test_database_enforces_one_video_and_remembers_aliases_under_concurrent_saves(tmp_path):
    store = AnalysisStore(tmp_path / "organ.sqlite3")
    store.initialize()
    first, second = record(), record()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store.save, item, {}, URL, 12.3) for item in [first, second]]
        saved = [future.result() for future in futures]
    assert saved[0]["id"] == saved[1]["id"]
    assert store.list(20, 0)["total"] == 1
    assert store.list(20, 0)["items"][0]["processing_seconds"] == 12.3
    assert store.find("https://vm.tiktok.com/SavedShort")["id"] == saved[0]["id"]
    with store.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO analyses (id, video_id) VALUES (?, ?)", (str(uuid.uuid4()), "123456789"))


def test_list_pagination_and_summary_do_not_expose_raw_actor_data(tmp_path):
    store = AnalysisStore(tmp_path / "organ.sqlite3")
    store.initialize()
    for index in range(3):
        store.save(record(str(index + 1)), {"private_raw_field": "not in list"}, URL.replace("123456789", str(index + 1)), 2)
    page = store.list(2, 0)
    assert page["total"] == 3 and len(page["items"]) == 2
    assert len(store.list(2, 2)["items"]) == 1
    assert "private_raw_field" not in json.dumps(page)


def test_cached_url_reuses_saved_result_without_token_or_analysis(monkeypatch, tmp_path):
    from backend import main
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    monkeypatch.setattr(main.shutil, "which", lambda _: None)
    work = Mock()
    monkeypatch.setattr(main, "analyze", work)
    with TestClient(main.app) as client:
        saved = record()
        main.store().save(saved, {}, URL, 10)
        for url in [URL + "?tracking=one", "https://m.tiktok.com/@renamed/video/123456789?tracking=two", "https://vm.tiktok.com/SavedShort/?tracking=three"]:
            response = client.post("/analyses", json={"url": url})
            assert response.status_code == 200
            assert response.json()["cached"] is True
            assert response.json()["result"]["id"] == saved.id
        work.assert_not_called()
        assert client.get("/analyses").json()["total"] == 1
        assert client.get("/analyses?limit=0").status_code == 422
        assert client.get("/analyses?offset=-1").status_code == 422


def test_duplicate_pending_links_share_the_same_job(monkeypatch, tmp_path):
    from backend import main
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "test-secret")
    monkeypatch.setattr(main.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    with TestClient(main.app) as client:
        submit = Mock()
        monkeypatch.setattr(main.executor, "submit", submit)
        first = client.post("/analyses", json={"url": URL + "?a=1"})
        second = client.post("/analyses", json={"url": "https://m.tiktok.com/@renamed/video/123456789?a=2"})
        assert first.status_code == second.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        assert submit.call_count == 1
