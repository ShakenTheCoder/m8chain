"""Resumable import of real, batch-collected English TikTok trend examples.

Usage: python -m backend.import_trends --directory .data/imports/english-trends-20261107
Collection files contain query, run_id, and items from the existing Apify actor.
No examples are synthesized and no model-generated trend labels affect grouping.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from dotenv import load_dotenv

from .pipeline import Settings, analyze_collected
from .storage import AnalysisStore
from .trends import words

GROUPS = {
    'jet2': ['jet2', 'jet 2'],
    'demure': ['demure', 'mindful'],
    'finance': ['man in finance', 'maninfinance'],
    'suspect': ['suspect challenge', 'suspectchallenge', 'suspect is'],
    'listen': ['we listen', 'welistenandwedontjudge', 'welistenwedontjudge'],
}


def matches_group(group, item, record):
    text = ' '.join([item.get('text') or '', (item.get('musicMeta') or {}).get('musicName') or '',
                     record.elements.transcript.text or '', record.visual.summary or '',
                     ' '.join(x.text for x in record.elements.on_screen_text.items)])
    normalized = ' '.join(words(text))
    return any(term in normalized for term in GROUPS[group])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--per-trend', type=int, default=7)
    parser.add_argument('--minutes', type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.per_trend <= 20 or not 1 <= args.minutes <= 120:
        parser.error('Use 1–20 clips per trend and a 1–120 minute execution budget.')
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / '.env')
    settings = Settings.from_env()
    database = AnalysisStore(root / '.data/organ.sqlite3')
    database.initialize()
    args.directory.mkdir(parents=True, exist_ok=True)
    state_path = args.directory / 'import-state.json'
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        records, _ = database.trend_records(limit=None)
        state = {'target_per_group': args.per_trend, 'baseline_ids': [r['video']['id'] for r in records],
                 'accepted': [], 'attempts': {}, 'status': 'running'}
    state['status'] = 'running'
    deadline = time.monotonic() + args.minutes * 60

    def persist():
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        temporary.replace(state_path)

    def progress(**event):
        print(json.dumps(event, ensure_ascii=False), flush=True)

    persist()
    while time.monotonic() < deadline:
        counts = Counter(x['group'] for x in state['accepted'])
        if all(counts[group] >= args.per_trend for group in GROUPS):
            state['status'] = 'complete'
            break
        pending_collection = False
        attempted = False
        for group in GROUPS:
            if counts[group] >= args.per_trend:
                continue
            path = args.directory / f'{group}-collection.json'
            if not path.exists():
                pending_collection = True
                continue
            collection = json.loads(path.read_text())
            items = collection['items']
            frequency = Counter(str((item.get('musicMeta') or {}).get('musicId')) for item in items)
            def priority(item):
                sound = str((item.get('musicMeta') or {}).get('musicId'))
                return (item.get('textLanguage') != 'en', -frequency[sound],
                        (item.get('videoMeta') or {}).get('duration') or 999)
            for item in sorted(items, key=priority):
                video_id = str(item.get('id') or '')
                if not video_id.isdigit() or video_id in state['attempts'] or video_id in state['baseline_ids']:
                    continue
                duration = (item.get('videoMeta') or {}).get('duration')
                if item.get('isSlideshow') or duration is None or not 0 < float(duration) <= 120:
                    state['attempts'][video_id] = {'group': group, 'status': 'ineligible_format_or_duration'}
                    persist()
                    continue
                if item.get('textLanguage') not in ('en', 'un', None, ''):
                    state['attempts'][video_id] = {'group': group, 'status': 'non_english_caption'}
                    persist()
                    continue
                url = item.get('webVideoUrl') or ''
                attempted = True
                started = time.monotonic()
                progress(event='analysis_started', group=group, video_id=video_id)
                try:
                    cached = database.find(url)
                    if cached:
                        from .models import Analysis
                        record = Analysis.model_validate(cached)
                    else:
                        def update(stage, message):
                            progress(event='stage', group=group, video_id=video_id, stage=stage)
                        record, _ = analyze_collected(item, collection['run_id'], url, settings, update)
                    reason = None
                    if record.language.code != 'en':
                        reason = 'english_speech_not_confirmed'
                    elif not record.elements.transcript.text:
                        reason = 'no_transcript'
                    elif not matches_group(group, item, record):
                        reason = 'trend_not_supported_by_content'
                    if reason:
                        state['attempts'][video_id] = {'group': group, 'status': reason, 'language': record.language.code}
                        progress(event='skipped', group=group, video_id=video_id, reason=reason)
                    else:
                        record.collection.discovery_queries = sorted(set(record.collection.discovery_queries + [collection['query']]))
                        saved = database.save(record, item, url, time.monotonic() - started)
                        entry = {'group': group, 'video_id': video_id, 'analysis_id': saved['id'], 'url': url,
                                 'language': record.language.code, 'status': record.status,
                                 'sound_id': record.elements.sound.id,
                                 'seconds': round(time.monotonic() - started, 2)}
                        state['accepted'].append(entry)
                        state['attempts'][video_id] = {'group': group, 'status': 'accepted'}
                        counts[group] += 1
                        progress(event='saved', group=group, count=counts[group], total=len(state['accepted']), seconds=entry['seconds'])
                except Exception as error:
                    # Avoid printing exception messages containing signed URLs or credentials.
                    state['attempts'][video_id] = {'group': group, 'status': 'failed', 'error_type': type(error).__name__}
                    progress(event='failed', group=group, video_id=video_id, error_type=type(error).__name__)
                persist()
                break  # Round-robin across the five groups as data becomes available.
        if not attempted:
            if pending_collection:
                time.sleep(5)
            else:
                state['status'] = 'needs_more_candidates'
                break
    else:
        state['status'] = 'time_budget_reached'
    persist()
    progress(event='import_stopped', status=state['status'], accepted=len(state['accepted']),
             counts=dict(Counter(x['group'] for x in state['accepted'])))


if __name__ == '__main__':
    main()
