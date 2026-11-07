from backend.import_trends import matches_group
from backend.models import Analysis
from backend.tests.test_trends import clip


def test_source_query_is_not_enough_to_label_a_clip():
    record = Analysis.model_validate(clip(1, script='I cooked pasta today'))
    assert not matches_group('finance', {'searchQuery':'looking for a man in finance'}, record)


def test_trend_content_can_be_supported_by_caption_transcript_or_sound():
    record = Analysis.model_validate(clip(1, script='I am looking for a man in finance'))
    assert matches_group('finance', {}, record)
    assert matches_group('jet2', {'musicMeta':{'musicName':'Nothing beats a Jet2 holiday'}}, record)
    assert matches_group('listen', {'text':'#welistenandwedontjudge'}, record)
