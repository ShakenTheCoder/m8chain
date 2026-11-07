from fastapi.testclient import TestClient

from backend.video_graph import extract_graph
from backend.trends import WEIGHTS
from backend.tests.test_trends import clip
from backend.tests.test_storage import record


def test_all_videos_including_isolated_and_duplicate_analyses():
    first = clip(1)
    duplicate = {**first, 'id': 'repeat'}
    result = extract_graph([first, duplicate, clip(2)])
    assert len(result['nodes']) == 2
    assert result['edges'] == []
    assert all(n['connection_count'] == 0 for n in result['nodes'])


def test_two_clips_are_enough_and_sound_edges_are_strong():
    result = extract_graph([clip(1, sound='same'), clip(2, sound='same')])
    assert len(result['edges']) == 1
    assert result['edges'][0]['strength'] == 'strong'
    assert result['edges'][0]['evidence'][0]['signal'] == 'sound'
    assert result['edges'][0]['score'] == round(WEIGHTS['sound'], 4)
    assert all(n['connection_count'] == 1 for n in result['nodes'])


def test_smaller_similarities_are_visible_but_not_claimed_as_strong_matches():
    result = extract_graph([clip(1, script='I cook fresh pasta for dinner tonight'),
                            clip(2, script='Fresh pasta tastes wonderful after a long day')])
    assert len(result['edges']) == 1
    edge = result['edges'][0]
    assert edge['strength'] == 'weak'
    assert edge['evidence'][0]['strength'] == 'weak'
    assert edge['evidence'][0]['value'] == 'fresh, pasta'
    assert extract_graph([clip(1, caption='for you'), clip(2, caption='for you')])['edges'] == []


def test_relationship_chain_keeps_every_direct_edge_without_inventing_one():
    records = [clip(1, sound='same'), clip(2, sound='same', script='Here is my morning routine'),
               clip(3, script='Here is my morning routine')]
    result = extract_graph(records)
    pairs = {(e['source'], e['target']) for e in result['edges']}
    assert ('clip-1', 'clip-2') in pairs
    assert ('clip-2', 'clip-3') in pairs
    assert ('clip-1', 'clip-3') not in pairs
    assert extract_graph(list(reversed(records))) == result


def test_graph_api_is_database_backed_and_updates_after_new_save(monkeypatch, tmp_path):
    from backend import main
    monkeypatch.setattr(main, 'DATA', tmp_path)
    with TestClient(main.app) as client:
        assert client.get('/graph').json()['nodes'] == []
        first = record('1')
        first.elements.sound.id = 'same'
        main.store().save(first, {}, first.video.url, 1)
        one = client.get('/graph').json()
        assert len(one['nodes']) == 1
        second = record('2')
        second.elements.sound.id = 'same'
        main.store().save(second, {}, second.video.url, 1)
        two = client.get('/graph').json()
        assert two['revision'] > one['revision']
        assert len(two['nodes']) == 2 and len(two['edges']) == 1
        assert 'graph' not in client.get('/trends').json()


def test_generic_platform_hashtags_do_not_connect_unrelated_videos():
    result = extract_graph([clip(1, caption='#fy #foryou #fyp #pulii #unghii'),
                            clip(2, caption='Who made this pizza #fy #foryou')])
    assert result['edges'] == []


def test_weak_graph_connections_do_not_establish_trends():
    from backend.trends import extract_trends
    records = [clip(1, sound='shared'), clip(2, sound='shared'),
               clip(3, script='I cook fresh pasta for dinner tonight'),
               clip(4, script='Fresh pasta tastes wonderful after a long day')]
    graph = extract_graph(records)
    trends = extract_trends(records)['trends']
    memberships = [set(c['analysis_id'] for c in trend['clips']) for trend in trends]
    assert len(trends) == 1
    for edge in graph['edges']:
        supported = any({edge['source'], edge['target']} <= members for members in memberships)
        assert supported == (edge['strength'] == 'strong')


def test_same_sound_makes_a_complete_set_of_pairwise_connections():
    records = [clip(i, sound='sound-id') for i in range(4)]
    # The ID, not differing/missing titles or the other elements, is decisive.
    records[0]['elements']['sound']['title'] = 'A title'
    records[1]['elements']['sound']['title'] = 'Another title'
    graph = extract_graph(records)
    assert len(graph['edges']) == 6
    assert all(n['connection_count'] == 3 for n in graph['nodes'])
    assert all(any(e['signal'] == 'sound' for e in edge['evidence']) for edge in graph['edges'])
    from backend.trends import extract_trends
    trends = extract_trends(records)['trends']
    assert len(trends) == 1 and len(trends[0]['clips']) == 4
