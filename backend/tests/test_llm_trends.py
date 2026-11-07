import pytest
from backend import llm_trends as llm
from backend.tests.test_trends import clip

REAL_ASK = llm.ask_model


def proposal(members, **extra):
    return llm.Proposal(title='Specific recurring format', concept='A repeatable creative mechanism supported by the clips.',
                        defining_pattern='Use a repeated setup and contrasting punchline.', cohesion='high',
                        members=members, execution_guide={'specific_to_trend':['Keep the setup'], 'steps':['Show setup', 'Reveal contrast'],
                        'can_adapt':['Change the setting'], 'review_before_posting':['Check context']}, **extra)


def support(clip_id, quote):
    return llm.Support(clip=clip_id, field='script', quote=quote, explanation='The spoken setup establishes the same repeated mechanism.')


def test_shared_audio_alone_never_becomes_a_concept(monkeypatch):
    def review(messages, config):
        return llm.Review(trends=[proposal([support('C001', 'invented setup'), support('C002', 'invented setup')])])
    monkeypatch.setattr(llm, 'ask_model', review)
    assert llm.extract_trends([clip(1,sound='same'),clip(2,sound='same')])['trends'] == []


def test_concept_can_cross_sound_ids_and_is_independently_reviewed(monkeypatch):
    records = [clip(1, sound='a',script='Nothing beats a holiday'),clip(2,sound='b',script='Nothing beats a holiday')]
    calls=[]
    def review(messages, config):
        calls.append(messages.copy())
        return llm.Review(trends=[proposal([support('C001','Nothing beats a holiday'),support('C002','Nothing beats a holiday')])])
    monkeypatch.setattr(llm, 'ask_model', review)
    result=llm.extract_trends(records)
    assert len(calls)==2
    assert result['grouped_videos']==2
    assert result['trends'][0]['classification']=='concept'
    assert 'matching_score' not in result['trends'][0]


def test_audit_can_reject_a_draft_and_no_fallback_is_published(monkeypatch):
    drafts=iter([llm.Review(trends=[proposal([support('C001','Repeated specific mechanism'),support('C002','Repeated specific mechanism')])]),llm.Review(trends=[])])
    monkeypatch.setattr(llm,'ask_model',lambda *args: next(drafts))
    assert llm.extract_trends([clip(1,script='Repeated specific mechanism'),clip(2,script='Repeated specific mechanism')])['trends']==[]


def test_unknown_ids_duplicate_members_and_inexact_quotes_are_rejected():
    sources,_=llm.library([clip(1,script='Exact source phrase'),clip(2,script='Exact source phrase')])
    for members in [[support('C001','Exact source phrase'),support('unknown','Exact source phrase')],
                    [support('C001','Exact source phrase'),support('C001','Exact source phrase')],
                    [support('C001','Invented phrase'),support('C002','Exact source phrase')]]:
        assert llm.grounded([proposal(members)],sources)==[]


def test_model_failure_is_explicit(monkeypatch):
    import httpx
    monkeypatch.setattr(llm.httpx,'post',lambda *args,**kwargs: (_ for _ in ()).throw(httpx.ConnectError('offline')))
    with pytest.raises(llm.TrendUnavailable):
        llm.extract_trends([clip(1),clip(2)])


def test_incomplete_model_output_is_never_published(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'done_reason':'length','message':{'content':'{"trends":[]}'}}
    monkeypatch.setattr(llm.httpx, 'post', lambda *a,**kw: Response())
    # Bypass the autouse unit model boundary to exercise the real HTTP adapter.
    with pytest.raises(llm.TrendUnavailable, match='output budget'):
        REAL_ASK([], llm.configuration())
