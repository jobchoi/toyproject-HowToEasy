"""Read the checked project tasks without treating plans as implemented features."""
from pathlib import Path
import re


def read_roadmap(path: Path):
    sections = []
    section = None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            section = {'title': line[3:].strip(), 'items': []}
            sections.append(section)
        match = re.match(r'^\s*(?:-|\d+\.)\s+\[([xX ])\]\s+(.+)$', line)
        if match and section is not None:
            section['items'].append({'done': match[1].lower() == 'x', 'title': match[2]})
    sections = [s for s in sections if s['items']]
    for section in sections:
        section['done'] = sum(item['done'] for item in section['items'])
        section['total'] = len(section['items'])
    return {'source': 'TASKS.md', 'sections': sections,
            'done': sum(s['done'] for s in sections), 'total': sum(s['total'] for s in sections)}
