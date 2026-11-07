from backend.tests.test_trends import clip
from backend.trends import extract_trends


def test_weak_topic_overlap_does_not_establish_a_trend():
    records = [clip(1, script='I cook fresh pasta for dinner tonight'),
               clip(2, script='Fresh pasta tastes wonderful after a long day')]
    assert extract_trends(records)['trends'] == []


def test_generic_visual_scene_is_not_a_trend():
    scene = 'A person stands indoors in a room facing the camera and talking'
    assert extract_trends([clip(1, visual=scene), clip(2, visual=scene)])['trends'] == []


def test_a_shared_phrase_cannot_join_disconnected_pairs():
    # The same short phrase occurs in unrelated longer scripts.
    records = [clip(1, script='Watch this happen cooking fresh pasta dinner sauce garlic kitchen'),
               clip(2, script='Watch this happen cooking fresh pasta dinner sauce garlic kitchen'),
               clip(3, script='Watch this happen mountain climbing ropes summit snow expedition'),
               clip(4, script='Watch this happen mountain climbing ropes summit snow expedition')]
    trends = extract_trends(records)['trends']
    assert all(len(t['clips']) == 2 for t in trends)
    assert len(trends) == 2
