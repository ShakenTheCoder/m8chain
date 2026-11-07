from copy import deepcopy
import pytest
from fastapi.testclient import TestClient

from backend.trends import WEIGHTS, extract_trends
from backend.tests.test_storage import record


def clip(index, sound=None, script=None, caption=None, visual=None, subtitles=None):
    result = record(str(index)).model_dump()
    result['id'] = f'clip-{index}'
    result['video']['creator_id'] = f'creator-{index}'
    result['elements']['post_description'] = caption
    result['elements']['sound']['id'] = sound
    result['elements']['transcript']['text'] = script
    result['visual']['summary'] = visual
    if subtitles:
        result['elements']['on_screen_text']['items'] = [{'text': subtitles}]
    return result


def test_sound_has_greatest_weight_and_exact_id_is_required():
    records = [clip(1, sound='sound-a'), clip(2, sound='sound-a'),
               clip(3, script='A surprisingly simple recipe for dinner'), clip(4, script='A surprisingly simple recipe for dinner')]
    result = extract_trends(records)
    assert len(result['trends']) == 2
    sound, script = result['trends']
    assert sound['classification'] == 'sound'
    assert sound['matching_score'] > script['matching_score']
    assert WEIGHTS['sound'] > max(v for k, v in WEIGHTS.items() if k != 'sound')
    assert sound['matching_score'] == round(35 / 90, 4)
    assert script['matching_score'] == round(30 / 90, 4)
    assert sum(WEIGHTS.values()) == pytest.approx(1)
    assert WEIGHTS['sound'] / WEIGHTS['script'] == pytest.approx(35 / 30)
    assert extract_trends([clip(1), clip(2)])['trends'] == []
    assert extract_trends([clip(1, sound='a'), clip(2, sound='b')])['trends'] == []


def test_duplicate_video_cannot_make_a_trend():
    first = clip(1, sound='same')
    duplicate = deepcopy(first)
    duplicate['id'] = 'another-analysis'
    assert extract_trends([first, duplicate])['trends'] == []


def test_different_cues_form_overlapping_trends_without_one_large_chain():
    a = clip(1, sound='same')
    b = clip(2, sound='same', script='Here is my morning routine')
    c = clip(3, script='Here is my morning routine')
    result = extract_trends([a, b, c])
    assert len(result['trends']) == 2
    members = [{c['analysis_id'] for c in t['clips']} for t in result['trends']]
    assert {'clip-1', 'clip-2'} in members
    assert {'clip-2', 'clip-3'} in members
    assert result['ungrouped_videos'] == 0


def test_all_text_and_visual_signals_and_evidence_backed_guide():
    text = 'Când ajungi acasă după ore'
    visual = 'A person enters a bright room carrying a blue bag and sits beside the wooden table'
    result = extract_trends([clip(1, script=text, caption=text, subtitles=text, visual=visual),
                             clip(2, script='Cand ajungi acasa dupa ore', caption=text, subtitles=text, visual=visual)])
    trend = result['trends'][0]
    assert trend['classification'] == 'mixed'
    assert {e['signal'] for e in trend['evidence']} == {'script', 'caption', 'subtitles', 'visual'}
    assert all(set(e['clip_ids']) == {'clip-1', 'clip-2'} for e in trend['evidence'])
    assert any('spoken script' in item for item in trend['execution_guide']['specific_to_trend'])
    assert any('cand ajungi acasa' in item for item in trend['execution_guide']['steps'])
    assert trend['creator_count'] == 2
    assert trend['status'] == 'candidate'
    assert extract_trends(list(reversed([clip(1, sound='same'), clip(2, sound='same')]))) == extract_trends([clip(1, sound='same'), clip(2, sound='same')])


def test_generic_short_captions_ignored_and_word_overlap_labeled_weak():
    assert extract_trends([clip(1, caption='For you'), clip(2, caption='For you')])['trends'] == []
    result = extract_trends([clip(1, script='I like food and cooking at home'), clip(2, script='Cooking food is a beautiful art')])
    assert result['trends'] == []


def test_trends_endpoint_reads_saved_records_and_exports_schema(monkeypatch, tmp_path):
    from backend import main
    monkeypatch.setattr(main, 'DATA', tmp_path)
    with TestClient(main.app) as client:
        assert client.get('/trends').json()['trends'] == []
        for index in [1, 2]:
            saved = record(str(index))
            saved.elements.sound.id = 'shared-audio'
            saved.elements.transcript.text = 'A repeated specific creative setup'
            main.store().save(saved, {}, saved.video.url, 1)
        response = client.get('/trends')
        assert response.status_code == 200
        data = response.json()
        assert data['total_saved_videos'] == data['grouped_videos'] == 2
        assert data['truncated'] is False
        assert len(data['trends']) == 1
        assert client.get('/trends/schema').json()['title'] == 'Trend'
        assert len(data['trends'][0]['execution_guide']['steps']) >= 3


def test_shared_sound_title_without_sound_ids_is_not_identity():
    records = [clip(1), clip(2)]
    for result in records:
        result['elements']['sound']['title'] = 'original sound'
    assert extract_trends(records)['trends'] == []


def test_explicit_storage_limit_and_endpoints_use_all_records(monkeypatch, tmp_path):
    from backend import main
    from backend.storage import AnalysisStore
    database = AnalysisStore(tmp_path / 'scan.sqlite3')
    database.initialize()
    for index in range(3):
        saved = record(str(index + 1))
        database.save(saved, {}, saved.video.url, 1)
    records, total = database.trend_records(2)
    assert len(records) == 2 and total == 3
    monkeypatch.setattr(main, 'store', lambda: database)
    with TestClient(main.app) as client:
        result = client.get('/trends').json()
        assert result['truncated'] is False
        assert result['total_saved_videos'] == 3
        assert result['scan_limit'] is None
        assert len(client.get('/graph').json()['nodes']) == 3


def test_each_new_save_updates_trends_without_visiting_page_and_reads_reuse_snapshot(monkeypatch, tmp_path):
    from unittest.mock import Mock
    from backend import storage
    database = storage.AnalysisStore(tmp_path / 'events.sqlite3')
    database.initialize()
    compute = Mock(wraps=storage.extract_trends)
    monkeypatch.setattr(storage, 'extract_trends', compute)
    first, second = record('1'), record('2')
    first.elements.sound.id = second.elements.sound.id = 'same-sound'
    first.elements.transcript.text = second.elements.transcript.text = 'A repeated specific creative setup'
    database.save(first, {}, first.video.url, 1)
    assert compute.call_count == 1
    # Read the persisted snapshot directly: no page/GET has triggered the rebuild.
    with database.connect() as connection:
        revision, computed, encoded = connection.execute('SELECT revision, computed_revision, result FROM trend_state').fetchone()
    assert revision == computed == 1
    assert '"trends": []' in encoded
    database.save(second, {}, second.video.url, 1)
    assert compute.call_count == 2
    snapshot = database.trend_snapshot()
    assert snapshot['revision'] == 2
    assert snapshot['grouped_videos'] == 2
    assert len(snapshot['trends']) == 1
    database.trend_snapshot()
    database.save(record('2'), {}, second.video.url, 1)
    assert compute.call_count == 2
    assert database.trend_snapshot()['revision'] == 2
    # Restart preserves the published snapshot instead of recalculating.
    database.initialize()
    assert database.trend_snapshot() == snapshot
    assert compute.call_count == 2


def test_failed_update_retains_analysis_and_retries_dirty_revision(monkeypatch, tmp_path):
    from unittest.mock import Mock
    from backend import storage
    database = storage.AnalysisStore(tmp_path / 'retry.sqlite3')
    database.initialize()
    real = storage.extract_trends
    compute = Mock(side_effect=RuntimeError('Temporary grouping error'))
    monkeypatch.setattr(storage, 'extract_trends', compute)
    saved = record('1')
    database.save(saved, {}, saved.video.url, 1)
    assert database.get(saved.id) is not None
    with database.connect() as connection:
        revision, computed = connection.execute('SELECT revision, computed_revision FROM trend_state').fetchone()
    assert revision != computed
    compute.side_effect = None
    compute.wraps = real
    monkeypatch.setattr(storage, 'extract_trends', real)
    assert database.trend_snapshot()['analyzed_videos'] == 1
    with database.connect() as connection:
        revision, computed = connection.execute('SELECT revision, computed_revision FROM trend_state').fetchone()
    assert revision == computed


def test_concurrent_saves_publish_latest_revision_without_lost_videos(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from backend.storage import AnalysisStore
    database = AnalysisStore(tmp_path / 'concurrent.sqlite3')
    database.initialize()
    records = [record('1'), record('2')]
    for item in records:
        item.elements.sound.id = 'same'
        item.elements.transcript.text = 'A repeated specific creative setup'
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(database.save, item, {}, item.video.url, 1) for item in records]
        for future in futures:
            future.result()
    result = database.trend_snapshot()
    assert result['revision'] == result['grouped_videos'] == 2
    assert len(result['trends']) == 1
