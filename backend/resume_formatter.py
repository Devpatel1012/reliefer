"""resume_formatter.py -- Structural post-processor for LLM-generated resume Markdown.
"""

import re
from typing import List, Tuple, Optional


def _clean_bullet_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalise_to_lines(raw: str) -> str:
    normalised = re.sub(r'\s*---+\s*', '\n', raw)
    normalised = re.sub(r'(?<!\n)(#{1,4}\s+)', r'\n\1', normalised)
    normalised = re.sub(r'^[ \t]{2,}([*•-]|[A-Z])', r'- \1', normalised, flags=re.MULTILINE)
    normalised = re.sub(r'^-\s*[*•-]\s*', '- ', normalised, flags=re.MULTILINE)
    return normalised


def _split_raw_into_sections(raw: str) -> dict:
    raw = _normalise_to_lines(raw)
    sections = {
        'header': [],
        'summary': [],
        'skills': [],
        'experience': [],
        'projects': [],
        'education': [],
        'achievements': [],
    }
    current_section = 'header'
    section_map = [
        (re.compile(r'^#{0,4}\s*(PROFESSIONAL\s+SUMMARY|SUMMARY|OBJECTIVE|ABOUT\s+ME)\s*$', re.IGNORECASE), 'summary'),
        (re.compile(r'^#{0,4}\s*(TECHNICAL\s+SKILLS|SKILLS)\s*$', re.IGNORECASE), 'skills'),
        (re.compile(r'^#{0,4}\s*(WORK\s+EXPERIENCE|EXPERIENCE|EMPLOYMENT)\s*$', re.IGNORECASE), 'experience'),
        (re.compile(r'^#{0,4}\s*(PROJECTS?)\s*$', re.IGNORECASE), 'projects'),
        (re.compile(r'^#{0,4}\s*(EDUCATION)\s*$', re.IGNORECASE), 'education'),
        (re.compile(r'^#{0,4}\s*(ACHIEVEMENTS?.*|CERTIFICATIONS?.*|AWARDS?.*)\s*$', re.IGNORECASE), 'achievements'),
    ]

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            sections[current_section].append('')
            continue

        matched = False
        for pattern, sec_name in section_map:
            if pattern.match(stripped):
                current_section = sec_name
                matched = True
                break

        if not matched:
            sections[current_section].append(line)

    return {k: '\n'.join(v).strip() for k, v in sections.items()}


def _parse_name_contact(header_block: str) -> Tuple[str, str]:
    name = ''
    contact = ''
    for line in header_block.splitlines():
        stripped = line.strip()
        if not name and stripped.startswith('# '):
            name = stripped[2:].strip()
        elif not name and len(stripped) > 0 and not '|' in stripped and not '@' in stripped and not stripped.startswith('##'):
            name = stripped
        elif '|' in stripped or '@' in stripped or 'linkedin' in stripped.lower() or 'github' in stripped.lower():
            if not contact:
                contact = stripped
    return name, contact


def _parse_experience_entries(block: str) -> List[dict]:
    entries = []
    current: Optional[dict] = None
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        is_heading = stripped.startswith('###')
        if not is_heading and re.search(r'\s@\s.+\|.+\d{4}', stripped) and len(stripped) > 15:
            is_heading = True

        if is_heading:
            if current:
                entries.append(current)
            heading_text = re.sub(r'^#{1,4}\s*', '', stripped).strip()
            current = {'heading': heading_text, 'bullets': []}
        elif re.match(r'^[-*•]\s+', stripped):
            if current is not None:
                bullet = _clean_bullet_text(re.sub(r'^[-*•]\s+', '', stripped))
                if bullet:
                    current['bullets'].append(bullet)
        elif current is not None and len(stripped) > 5 and not stripped.startswith('##'):
            bullet = _clean_bullet_text(stripped)
            if bullet:
                current['bullets'].append(bullet)

    if current:
        entries.append(current)
    return entries


def _parse_project_entries(block: str) -> List[dict]:
    entries = []
    current: Optional[dict] = None
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        is_heading = stripped.startswith('###')
        is_bare_heading = (
            not is_heading
            and current is None
            and not re.match(r'^[-*•]', stripped)
            and not re.match(r'^\*?\*?tech\s+stack', stripped, re.IGNORECASE)
            and len(stripped) > 3
        )

        if is_heading or is_bare_heading:
            if current:
                entries.append(current)
            heading_text = re.sub(r'^#{1,4}\s*', '', stripped).strip()
            if ' | ' in heading_text:
                parts = heading_text.split(' | ', 1)
                current = {'name': parts[0].strip(), 'tech_stack': parts[1].strip(), 'bullets': []}
            else:
                current = {'name': heading_text, 'tech_stack': '', 'bullets': []}
        elif re.match(r'^\*?\*?tech\s+stack\*?\*?:?', stripped, re.IGNORECASE):
            ts = re.sub(r'^\*?\*?tech\s+stack\*?\*?:?\s*', '', stripped, flags=re.IGNORECASE).strip('* \t')
            if current:
                current['tech_stack'] = ts
        elif re.match(r'^[-*•]\s+', stripped):
            if current is not None:
                bullet = _clean_bullet_text(re.sub(r'^[-*•]\s+', '', stripped))
                if bullet:
                    current['bullets'].append(bullet)
        elif current is not None and not re.match(r'^[-*•]', stripped):
            if re.match(r'^[A-Za-z0-9][A-Za-z0-9\-_\.]*$', stripped) or stripped.endswith('-'):
                entries.append(current)
                current = {'name': stripped, 'tech_stack': '', 'bullets': []}

    if current:
        entries.append(current)
    return entries


def _parse_skill_lines(block: str) -> List[str]:
    lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            clean = re.sub(r'^[-*•]\s*', '', stripped).strip()
            if clean:
                lines.append(clean)
    return lines


def _parse_achievements(block: str) -> List[str]:
    items = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            text = re.sub(r'^[-*•]\s*', '', stripped).strip()
            if text:
                items.append(text)
    return items


def _parse_education_lines(block: str) -> List[str]:
    lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            clean = re.sub(r'^[-*•]\s*', '', stripped).strip()
            if clean:
                lines.append(clean)
    return lines


def _parse_summary(block: str) -> str:
    lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            lines.append(stripped)
    return ' '.join(lines).strip()


def _fmt_header(block: str) -> str:
    name, contact = _parse_name_contact(block)
    lines = []
    if name:
        lines.append(f'# {name}')
    if contact:
        lines.append(contact)
    return '\n'.join(lines)


def _fmt_summary(block: str) -> str:
    text = _parse_summary(block)
    if not text:
        return ''
    return f'## PROFESSIONAL SUMMARY\n\n{text}'


def _fmt_skills(block: str) -> str:
    skill_lines = _parse_skill_lines(block)
    if not skill_lines:
        return ''
    formatted = '\n'.join(f'- {s}' for s in skill_lines)
    return f'## TECHNICAL SKILLS\n\n{formatted}'


def _fmt_experience(block: str) -> str:
    entries = _parse_experience_entries(block)
    if not entries:
        return ''
    parts = ['## WORK EXPERIENCE']
    for entry in entries:
        parts.append('')
        parts.append(f'### {entry["heading"]}')
        for bullet in entry['bullets']:
            parts.append(f'- {bullet}')
    return '\n'.join(parts)


def _fmt_projects(block: str) -> str:
    entries = _parse_project_entries(block)
    if not entries:
        return ''
    parts = ['## PROJECTS']
    for entry in entries:
        parts.append('')
        parts.append(f'### {entry["name"]}')
        if entry['tech_stack']:
            parts.append(f'**Tech Stack:** {entry["tech_stack"]}')
        for bullet in entry['bullets']:
            parts.append(f'- {bullet}')
    return '\n'.join(parts)


def _fmt_education(block: str) -> str:
    lines = _parse_education_lines(block)
    if not lines:
        return ''
    formatted = '\n'.join(f'- {l}' if not l.startswith('-') else l for l in lines)
    return f'## EDUCATION\n\n{formatted}'


def _fmt_achievements(block: str) -> str:
    items = _parse_achievements(block)
    if not items:
        return ''
    formatted = '\n'.join(f'- {item}' for item in items)
    return f'## ACHIEVEMENTS & CERTIFICATIONS\n\n{formatted}'


_MAJOR_SECTION_PREFIXES = (
    '## PROFESSIONAL SUMMARY',
    '## TECHNICAL SKILLS',
    '## WORK EXPERIENCE',
    '## PROJECTS',
    '## EDUCATION',
    '## ACHIEVEMENTS',
)


def format_resume(raw_llm_output: str) -> str:
    if not raw_llm_output:
        return ''
    sections = _split_raw_into_sections(raw_llm_output)
    ordered_formatters = [
        ('header',       _fmt_header),
        ('summary',      _fmt_summary),
        ('skills',       _fmt_skills),
        ('experience',   _fmt_experience),
        ('projects',     _fmt_projects),
        ('education',    _fmt_education),
        ('achievements', _fmt_achievements),
    ]
    blocks = []
    for key, formatter in ordered_formatters:
        formatted = formatter(sections[key])
        if formatted.strip():
            blocks.append(formatted.strip())
    result_parts = []
    for i, block in enumerate(blocks):
        if i == 0:
            result_parts.append(block)
        else:
            result_parts.append('\n\n---\n\n')
            result_parts.append(block)
    return '\n'.join(result_parts).strip()
