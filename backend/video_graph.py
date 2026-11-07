"""Pairwise video connections, including weaker, explicitly labeled similarities."""
from itertools import combinations

from .trends import WEIGHTS, TEXT_MATCHING, relationship, prepare, prepare_semantics

GRAPH_METHOD = "video-relationships-v5-supported-trends"


def extract_graph(records):
    unique = {}
    for record in sorted(records, key=lambda r: r['id']):
        video_id = record.get('video', {}).get('id')
        if video_id and video_id not in unique:
            unique[video_id] = prepare(record)
    items = list(unique.values())
    prepare_semantics(items)
    nodes = []
    for item in items:
        record = item['record']
        video = record['video']
        nodes.append({'id': record['id'], 'video_id': video['id'], 'url': video['url'],
                      'label': item['texts']['caption'] or item['texts']['script'][:100] or f"Video {video['id']}",
                      'description': item['texts']['visual'] or record.get('description', {}).get('text'),
                      'creator_id': video.get('creator_id'), 'status': record.get('status'),
                      'connection_count': 0})
    edges = []
    for i, j in combinations(range(len(items)), 2):
        a, b = items[i], items[j]
        score, items_evidence = relationship(a, b)
        evidence = [item.model_dump() for item in items_evidence]
        strong = any(item.strength == "strong" for item in items_evidence)
        if not evidence:
            continue
        edges.append({'id': f"{nodes[i]['id']}:{nodes[j]['id']}", 'source': nodes[i]['id'], 'target': nodes[j]['id'],
                      'strength': 'strong' if strong else 'weak', 'score': round(score, 4), 'evidence': evidence})
        nodes[i]['connection_count'] += 1
        nodes[j]['connection_count'] += 1
    return {'schema_version': '1.0', 'method': GRAPH_METHOD, 'nodes': nodes, 'edges': edges,
            'signal_weights': WEIGHTS, 'text_matching': TEXT_MATCHING, 'limitations': [
                'Text similarity is 50% word overlap and 50% multilingual meaning similarity.',
                'Solid lines show strong matching evidence; dashed lines show weaker combined similarities.',
                'Weak similarities are exploratory connections, not trend membership. Trends require strong support for a shared cue.',
                'Sound identity uses platform IDs. Visual connections compare inferred frame descriptions.',
                'Connections are pairwise; a path through another video is not a direct match.']}
