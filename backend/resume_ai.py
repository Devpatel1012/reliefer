"""resume_ai.py — Reliefer resume generation engine.

Pipeline:
  1. fetch_job_description_from_url() → raw JD text
  2. extract_keywords()              → top-N ATS keywords
  3. curate_profile_for_job()        → filter & rank profile sections
  4. build_prompt()                  → tight, structured LLM prompt
  5. call_huggingface()              → LLM output (+ structured fallback)
  6. _post_process_resume()          → strip emojis / N/A / artefacts
  7. render_pdf()                    → polished PDF bytes
"""

import html
import json
import logging
import os
import re
import time
import unicodedata
from collections import Counter
from io import BytesIO
from typing import Any

import models
import requests
from fastapi import HTTPException
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from resume_formatter import format_resume as _format_resume_structure

logger = logging.getLogger("reliefer.resume_ai")

DEFAULT_HF_MODEL = os.getenv("HUGGINGFACE_DEFAULT_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "is", "are", "was", "were", "be", "been", "being", "as", "at",
    "by", "from", "that", "this", "these", "those", "it", "its", "we",
    "you", "your", "will", "should", "must", "our", "their", "who", "which",
    "than", "into", "have", "has", "had", "not", "such", "etc", "role",
    "job", "work", "team", "company", "years", "year", "experience",
    "candidate", "candidates", "ability", "including", "using", "able",
}

TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/-]{1,}")

# Patterns for garbage projects that should NEVER appear on a resume
GARBAGE_PROJECT_RE = re.compile(
    r"(leetcode|hackerrank|codeforces|competitive.?programm|hello.?world"
    r"|\.github\.io$)",
    re.IGNORECASE,
)

# Practice / tutorial repos get a scoring penalty — not filtered but deprioritised
PRACTICE_PROJECT_RE = re.compile(
    r"(practice[-_]?$|[-_]practice$|tutorial|learning[-_]?repo|my[-_]?practice|solved[-_]?problems)",
    re.IGNORECASE,
)

# Projects that are trivially useless
TRIVIAL_DESC_RE = re.compile(
    r"^(public github repository with 0 stars\.?|public github repository\.?|"
    r"this repo contains the solved leetcode problems.*|)$",
    re.IGNORECASE,
)

# N/A-like placeholder strings
NA_RE = re.compile(
    r"^\s*(n/?a|na|none|null|undefined|–|—|-|not\s+applicable)\s*$",
    re.IGNORECASE,
)

# Emoji and special unicode symbol ranges
_EMOJI_RANGES = [
    (0x1F300, 0x1FAFF),  # Miscellaneous Symbols, Emoticons, etc.
    (0x2600, 0x26FF),    # Misc Symbols
    (0x2700, 0x27BF),    # Dingbats
    (0xFE00, 0xFE0F),    # Variation Selectors
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
]

# Skill category labels that get embedded in skill names during resume parsing
# e.g. "Tech Stack: Python, C, CUDA C++, PyTorch" stored as ONE skill name
CATEGORY_PREFIX_RE = re.compile(
    r"^(tech(?:nical)?\s*stack|languages?|frameworks?|tools?|cloud|ml\s*(?:skills?)?|"
    r"ai|databases?|libraries|technologies|skills?|platforms?)"
    r"\s*[:\-–]\s*",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _strip_emojis(text: str) -> str:
    """Remove emoji and decorative unicode symbols from text."""
    if not text:
        return text
    result = []
    for ch in text:
        cp = ord(ch)
        cat = unicodedata.category(ch)
        in_emoji_range = any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)
        # Keep normal letters, numbers, punctuation; drop So (Symbol,Other) and emoji ranges
        if in_emoji_range or (cat == "So"):
            result.append(" ")
        else:
            result.append(ch)
    return re.sub(r"\s{2,}", " ", "".join(result)).strip()


def _clean_na(value: str | None) -> str:
    """Return '' if value is None, empty, or a placeholder like N/A."""
    if not value:
        return ""
    stripped = value.strip()
    if NA_RE.match(stripped):
        return ""
    return stripped


def _clean_text(text: str | None) -> str:
    """Strip emojis and N/A from a text field."""
    return _strip_emojis(_clean_na(text or ""))


def _score_relevance(text: str, keywords: list[str]) -> int:
    """Count how many job keywords appear in text (case-insensitive)."""
    if not text or not keywords:
        return 0
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def _expand_skill_entry(raw_name: str, raw_cat: str) -> list[tuple[str, str]]:
    """
    If a skill name looks like 'Tech Stack: Python, C++, PyTorch' (a common
    artefact from resume auto-parsing), split it into individual skill tokens.

    Returns a list of (skill_name, category) tuples.
    """
    m = CATEGORY_PREFIX_RE.match(raw_name)
    if m:
        # The prefix becomes the category label
        prefix = raw_name[:m.end()].rstrip(': -–').strip().title()
        remainder = raw_name[m.end():].strip()
        # Split on comma or semicolon, then clean each token
        raw_tokens = re.split(r",\s*", remainder)
        valid = []
        for t in raw_tokens:
            t = t.strip().strip("[]")
            # Remove trailing parenthetical annotations like "(Basics)", "(v2)"
            t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip()
            if t and len(t) > 1:
                valid.append(t)
        if valid:
            return [(t, prefix or raw_cat) for t in valid]
    # No prefix found — return as-is
    return [(raw_name, raw_cat)]


def _is_garbage_project(p: models.Project) -> bool:
    """Return True for projects that should be excluded from any resume."""
    title = (p.title or "").strip()
    desc = _clean_text(p.description or "")
    tech = _clean_text(p.technologies or "")

    # Bare username repo (e.g. "Devpatel1012") — only alphanumeric, no hyphens/underscores as separators in desc
    if re.match(r"^[A-Za-z0-9]+$", title) and not tech and not desc:
        return True
    # Matches known garbage patterns in title
    if GARBAGE_PROJECT_RE.search(title):
        return True
    # Trivial description + no tech = filler
    if TRIVIAL_DESC_RE.match(desc) and not tech:
        return True
    # Explicitly meaningless
    return bool(title.lower().endswith(".github.io"))


# ─────────────────────────────────────────────────────────────────────────────
# Job description fetching & keyword extraction
# ─────────────────────────────────────────────────────────────────────────────

def fetch_job_description_from_url(url: str) -> str:
    """Fetch a job description from a URL."""
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Reliefer/1.0; +https://reliefer.app)",
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
            },
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=400, detail=f"Could not fetch job URL: {exc}")

    html = resp.text

    meta_patterns = [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\'<>]+)["\']',
        r'<meta[^>]+content=["\']([^"\'<>]+)["\'][^>]+property=["\']og:description["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\'<>]+)["\']',
        r'<meta[^>]+content=["\']([^"\'<>]+)["\'][^>]+name=["\']description["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content="([^"]+)"',
        r'<meta[^>]+content="([^"]+)"[^>]+property=["\']og:description["\']',
        r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
        r'<meta[^>]+content="([^"]+)"[^>]+name="description"',
    ]
    for pat in meta_patterns:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            text = m.group(1)
            text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                       .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
                       .replace("\\n", "\n").replace("\\t", " "))
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 200:
                return text

    text = TAG_RE.sub(" ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_keywords(text: str, top_n: int = 30) -> list[str]:
    """Extract the most relevant keywords from a job description."""
    text = (text.replace("&amp;", "&").replace("&#39;", "'").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"').replace("&nbsp;", " "))
    words = [w.lower() for w in WORD_RE.findall(text)]
    words = [w for w in words if w not in STOPWORDS and len(w) > 2 and not w.isdigit()]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(top_n)]


# ─────────────────────────────────────────────────────────────────────────────
# Pre-curation engine — selects best matching content before LLM call
# ─────────────────────────────────────────────────────────────────────────────

def curate_profile_for_job(
    user: models.User,
    keywords: list[str],
    max_projects: int = 3,
    max_experience: int = 4,
) -> dict[str, Any]:
    """
    Score, filter, and rank the user's profile data against job keywords.

    Returns a dict with clean, curated sections ready for prompt injection.
    """
    # ── Skills ─────────────────────────────────────────────────────────────
    skill_by_cat: dict[str, list[str]] = {}
    seen_skills: set = set()
    for s in (user.skills or []):
        raw_name = _clean_text(s.name or "")
        raw_cat = _clean_text(s.category or "") or "Technical"
        if not raw_name:
            continue
        # Expand compound skill entries (e.g. "Tech Stack: Python, C++, PyTorch")
        for skill_name, skill_cat in _expand_skill_entry(raw_name, raw_cat):
            if skill_name.lower() in seen_skills:
                continue
            seen_skills.add(skill_name.lower())
            skill_by_cat.setdefault(skill_cat, []).append(skill_name)

    # ── Experience ─────────────────────────────────────────────────────────
    seen_exp: set = set()
    scored_exp = []
    for e in (user.experience or []):
        role = _clean_text(e.role or "")
        company = _clean_text(e.company or "")
        desc = _clean_text(e.description or "")
        key = f"{role.lower()}@{company.lower()}"
        if key in seen_exp or not role:
            continue
        seen_exp.add(key)

        end_raw = _clean_text(e.end_date or "")
        end = "Present" if e.is_current else (end_raw or "")
        start = _clean_text(e.start_date or "")

        # Score by keyword overlap in role + company + description
        combined = f"{role} {company} {desc}"
        score = _score_relevance(combined, keywords)

        scored_exp.append({
            "role": role,
            "company": company,
            "start": start,
            "end": end,
            "is_current": bool(e.is_current),
            "description": desc,
            "score": score,
        })

    # Sort: current first, then by relevance score
    scored_exp.sort(key=lambda x: (x["is_current"], x["score"]), reverse=True)
    selected_exp = scored_exp[:max_experience]

    # ── Projects ───────────────────────────────────────────────────────────
    seen_projs: set = set()
    scored_projs = []
    for p in (user.projects or []):
        title = _clean_text(p.title or "")
        if not title or title.lower() in seen_projs:
            continue
        seen_projs.add(title.lower())
        if _is_garbage_project(p):
            continue

        desc = _clean_text(p.description or "")
        tech = _clean_text(p.technologies or "")

        combined = f"{title} {desc} {tech}"
        score = _score_relevance(combined, keywords)

        # Boost: meaningful description
        if len(desc) > 60:
            score += 2
        elif len(desc) > 30:
            score += 1
        # Boost: has technologies listed
        if tech:
            score += 1
        # Penalty: practice / tutorial repos (learning exercises, not achievements)
        if PRACTICE_PROJECT_RE.search(title):
            score -= 2
        # Penalty: README-only intro text (starts with generic welcome phrases)
        if re.match(r'^(welcome to|this (repo|repository) (contains|is)|a (classic|simple))', desc, re.IGNORECASE):
            score -= 1

        scored_projs.append({
            "title": title,
            "description": desc,
            "technologies": tech,
            "link": _clean_text(p.link or ""),
            "score": score,
        })

    scored_projs.sort(key=lambda x: x["score"], reverse=True)
    selected_projs = scored_projs[:max_projects]

    # ── Education ──────────────────────────────────────────────────────────
    education = []
    for e in (user.education or []):
        institution = _clean_text(e.institution or "")
        degree = _clean_text(e.degree or "")
        field = _clean_text(e.field_of_study or "")
        start_yr = _clean_text(e.start_year or "")
        end_yr = _clean_text(e.end_year or "")
        gpa = _clean_text(e.gpa or "")
        if not institution and not degree:
            continue
        education.append({
            "institution": institution,
            "degree": degree,
            "field": field,
            "start_year": start_yr,
            "end_year": end_yr,
            "gpa": gpa,
        })

    # ── Achievements ───────────────────────────────────────────────────────
    achievements = []
    for a in (user.achievements or []):
        title = _clean_text(a.title or "")
        desc = _clean_text(a.description or "")
        if not title:
            continue
        achievements.append({"title": title, "description": desc})

    return {
        "name": _clean_text(user.name or "Candidate"),
        "email": _clean_text(user.email or ""),
        "profession": _clean_text(user.profession or ""),
        "interest": _clean_text(user.interest or ""),
        "skill_by_cat": skill_by_cat,
        "experience": selected_exp,
        "projects": selected_projs,
        "education": education,
        "achievements": achievements,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Profile text builder (curated, clean)
# ─────────────────────────────────────────────────────────────────────────────

def build_curated_profile_text(curated: dict[str, Any]) -> str:
    """
    Build a clean, structured profile text block from the curated profile dict.
    No N/A values, no emojis, no raw markdown artefacts.
    """
    parts: list[str] = []

    # Meta
    meta = []
    if curated["profession"]:
        meta.append(f"Profession: {curated['profession']}")
    if curated["interest"]:
        meta.append(f"Target Domain: {curated['interest']}")
    if meta:
        parts.append(" | ".join(meta))

    # Skills
    skill_by_cat = curated["skill_by_cat"]
    if skill_by_cat:
        lines = []
        for cat, names in skill_by_cat.items():
            lines.append(f"  {cat}: {', '.join(names)}")
        parts.append("SKILLS:\n" + "\n".join(lines))

    # Experience
    exp_list = curated["experience"]
    if exp_list:
        exp_blocks = []
        for i, e in enumerate(exp_list, 1):
            block = [f"=== EXPERIENCE {i} ==="]
            block.append(f"Role: {e['role']}")
            if e["company"]:
                block.append(f"Company: {e['company']}")
            period_parts = []
            if e["start"]:
                period_parts.append(e["start"])
            if e["end"]:
                period_parts.append(e["end"])
            if period_parts:
                block.append(f"Period: {' – '.join(period_parts)}")
            elif e["is_current"]:
                block.append("Period: Present (current role)")
            if e["description"]:
                block.append(f"Description: {e['description']}")
            exp_blocks.append("\n".join(block))
        parts.append("WORK EXPERIENCE:\n" + "\n\n".join(exp_blocks))

    # Projects
    proj_list = curated["projects"]
    if proj_list:
        proj_blocks = []
        for i, p in enumerate(proj_list, 1):
            block = [f"=== PROJECT {i} ==="]
            block.append(f"Name: {p['title']}")
            if p["technologies"]:
                block.append(f"Technologies: {p['technologies']}")
            if p["description"]:
                block.append(f"Description: {p['description']}")
            if p["link"]:
                block.append(f"Link: {p['link']}")
            proj_blocks.append("\n".join(block))
        parts.append("PROJECTS (pre-selected, best matches for this role):\n" + "\n\n".join(proj_blocks))

    # Education
    edu_list = curated["education"]
    if edu_list:
        edu_lines = []
        for e in edu_list:
            line_parts = []
            if e["degree"]:
                line_parts.append(e["degree"])
            if e["field"]:
                line_parts.append(f"in {e['field']}")
            if e["institution"]:
                line_parts.append(f"at {e['institution']}")
            yr_parts = []
            if e["start_year"]:
                yr_parts.append(e["start_year"])
            if e["end_year"]:
                yr_parts.append(e["end_year"])
            if yr_parts:
                line_parts.append(f"({' – '.join(yr_parts)})")
            if e["gpa"]:
                line_parts.append(f"| CGPA: {e['gpa']}")
            edu_lines.append("  " + " ".join(line_parts))
        parts.append("EDUCATION:\n" + "\n".join(edu_lines))

    # Achievements
    ach_list = curated["achievements"]
    if ach_list:
        ach_lines = []
        for a in ach_list:
            entry = f"  - {a['title']}"
            if a["description"]:
                entry += f": {a['description']}"
            ach_lines.append(entry)
        parts.append("ACHIEVEMENTS & CERTIFICATIONS:\n" + "\n".join(ach_lines))

    return "\n\n".join(parts) if parts else "No profile data provided."


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_profile_summary(user: models.User) -> str:
    """Legacy helper kept for backward compat — wraps curate + build."""
    curated = curate_profile_for_job(user, keywords=[])
    return build_curated_profile_text(curated)


def build_prompt(
    user: models.User,
    job_description: str,
    keywords: list[str],
    template_content: str | None,
) -> str:
    curated = curate_profile_for_job(user, keywords)
    profile_text = build_curated_profile_text(curated)
    keyword_line = ", ".join(keywords[:25]) if keywords else "N/A"
    name = curated["name"]
    n_exp = len(curated["experience"])
    n_proj = len(curated["projects"])

    output_format = (
        f"Follow this exact resume structure:\n{template_content}\n\n"
        if template_content
        else (
            "OUTPUT FORMAT — produce a clean Markdown resume in this exact section order:\n"
            "1. # [Full Name]\n"
            "2. Contact line: email | location | linkedin | github\n"
            "3. ## PROFESSIONAL SUMMARY (3–4 sentences, specific to this role, mentions key skills)\n"
            "4. ## TECHNICAL SKILLS (grouped by category, e.g. '- ML Frameworks: PyTorch, Scikit-learn')\n"
            f"5. ## WORK EXPERIENCE ({n_exp} entries provided below — use ALL of them; each: ### Role @ Company | Period, then max 3 to 4 bullets starting with -)\n"
            f"6. ## PROJECTS ({n_proj} projects provided below — use ALL of them; each: ### Project Name | Tech Stack, then max 3 to 4 bullets starting with -)\n"
            "7. ## EDUCATION\n"
            "8. ## ACHIEVEMENTS & CERTIFICATIONS (include all listed)\n"
            "Use --- between major sections. Use **bold** for key metrics and tech names.\n\n"
        )
    )

    return f"""You are an expert ATS-optimized resume writer with 15+ years of experience placing candidates at top tech companies.

══════════════════════════════════════════
ABSOLUTE RULES — VIOLATING ANY RULE = REJECTED OUTPUT
══════════════════════════════════════════
1. NEVER output "N/A", "n/a", "None", "null", "undefined", "–" as a standalone value. If data is missing, OMIT that field entirely — do NOT write "N/A" or dashes.
2. NEVER include emojis (🚀, 👋, 🎯, etc.), unicode bullets (●, ■, ▶), or decorative symbols. Use ONLY plain ASCII hyphens "-" for bullets.
3. EVERY bullet point in Experience and Projects MUST start with a strong action verb: Developed, Engineered, Architected, Built, Designed, Implemented, Optimized, Automated, Achieved, Deployed, Integrated, Reduced, Improved, Led, Streamlined.
4. EVERY experience bullet and project bullet MUST include at least one concrete, quantifiable outcome or specific technical detail. Examples: "achieving 85% accuracy across 12 classes", "reducing inference time by 40%", "processing 4,000+ downloads in the first month", "scoring METEOR 0.33".
5. Experience heading format MUST be: ### [Role] @ [Company] | [Start] – [End or Present]
   If a date is not known, OMIT the date entirely from the heading — do NOT write "N/A" or "–".
6. Project heading format MUST be: ### [Project Name]
   Then immediately: **Tech Stack:** [comma-separated techs]
7. Education MUST show: [Degree] in [Field] at [Institution] ([Years]) — include CGPA/GPA if available.
8. DO NOT duplicate any experience or project entry. Each entry appears exactly once.
9. Output ONLY the resume. Do NOT include any preamble, "Here is your resume", or closing notes.
10. DO NOT add experiences or projects that are not in the candidate profile. Be factual.
11. EXACTLY max 3 to 4 bullet points for each Experience and Project entry. Do not over-explain.
12. ALWAYS leave a blank line before starting a new heading (e.g. before ### and ##).

══════════════════════════════════════════
ATS KEYWORD INTEGRATION
══════════════════════════════════════════
Weave these target keywords naturally throughout the resume (especially in Summary and bullets):
{keyword_line}

══════════════════════════════════════════
{output_format}══════════════════════════════════════════
CANDIDATE NAME: {name}

--- CANDIDATE PROFILE (pre-curated for this role) ---
{profile_text}

--- TARGET JOB DESCRIPTION ---
{job_description[:3000]}

Now write the complete, job-tailored resume for {name}:"""


# ─────────────────────────────────────────────────────────────────────────────
# Post-processing: clean LLM output
# ─────────────────────────────────────────────────────────────────────────────

# Regex to catch N/A-like fragments in output lines
_NA_IN_LINE_RE = re.compile(
    r"\s*[\|–—-]\s*(n/?a|none|null|undefined)\b"      # "| N/A" or "– None"
    r"|\b(n/?a|none|null|undefined)\s*[\|–—]"          # "N/A |"
    r"|^\s*[-•]\s*(n/?a|none|null)\s*$"                # standalone bullet
    r"|\(n/?a\s*[–—-]\s*n/?a\)",                       # "(N/A – N/A)"
    re.IGNORECASE,
)
_LONELY_NA_RE = re.compile(r"\bN/?A\b", re.IGNORECASE)


def _post_process_resume(text: str) -> str:
    """
    Clean up LLM output:
    - Strip emojis
    - Remove standalone N/A occurrences
    - Remove empty heading lines
    - Normalise excessive blank lines
    """
    # 1. Strip emojis and unicode symbols
    text = _strip_emojis(text)

    # 2. Process line by line
    clean_lines: list[str] = []
    for line in text.splitlines():
        # Remove "| N/A – N/A" and similar fragments
        line = _NA_IN_LINE_RE.sub("", line)
        # Remove dangling "N/A" that remain
        line = re.sub(r"\s*[|–—-]\s*N/?A\b\s*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\bN/?A\b\s*[|–—-]\s*", "", line, flags=re.IGNORECASE)
        
        stripped = line.strip()
        
        if not stripped:
            clean_lines.append(line)
            continue
            
        # Preserve markdown horizontal rules (---)
        if stripped.startswith("---") and len(stripped.replace("-", "")) == 0:
            clean_lines.append(line)
            continue
            
        # Remove lines that are ONLY "N/A" or punctuation
        if re.match(r"^[-–—|N/A\s]*$", stripped, re.IGNORECASE) and len(stripped) < 5:
            continue
            
        # Remove unicode decorative bullets mid-line
        line = re.sub(r"[●■▶►◆▪]", "-", line)
        clean_lines.append(line)

    # 3. Collapse 3+ consecutive blank lines into 2
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(clean_lines))
    return result.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Structured fallback (no LLM)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_section(prompt: str, start_marker: str, end_marker: str) -> str:
    try:
        start = prompt.index(start_marker) + len(start_marker)
        end = prompt.index(end_marker, start) if end_marker in prompt[start:] else len(prompt)
        return prompt[start:end].strip()
    except ValueError:
        return ""


def generate_structured_resume_fallback(prompt: str) -> str:
    """
    Build a clean resume directly from the structured candidate profile embedded
    in the prompt — used only when ALL LLM API calls fail.
    """
    # Extract name
    name = "Candidate"
    for line in prompt.split("\n"):
        if "CANDIDATE NAME:" in line:
            name = line.split("CANDIDATE NAME:")[-1].strip()
            break

    # Extract profile block
    profile_raw = _parse_section(
        prompt, "--- CANDIDATE PROFILE (pre-curated for this role) ---", "--- TARGET JOB DESCRIPTION ---"
    )
    if not profile_raw:
        profile_raw = _parse_section(prompt, "--- CANDIDATE PROFILE ---", "--- TARGET JOB DESCRIPTION ---")

    jd_raw = _parse_section(prompt, "--- TARGET JOB DESCRIPTION ---", "Now write")

    # ── Parse the structured profile text ──────────────────────────────────
    skills_lines: list[str] = []
    exp_blocks: list[dict] = []
    proj_blocks: list[dict] = []
    edu_lines: list[str] = []
    ach_lines: list[str] = []

    current_section = None
    current_block: dict = {}

    for line in profile_raw.splitlines():
        s = line.strip()
        if s.startswith("SKILLS:"):
            current_section = "skills"
            continue
        elif s.startswith("WORK EXPERIENCE:"):
            current_section = "exp"
            continue
        elif s.startswith("PROJECTS ("):
            current_section = "proj"
            continue
        elif s.startswith("EDUCATION:"):
            current_section = "edu"
            continue
        elif s.startswith("ACHIEVEMENTS"):
            current_section = "ach"
            continue

        if not s:
            continue

        if current_section == "skills":
            skills_lines.append(s.lstrip("- ").strip())

        elif current_section == "exp":
            if s.startswith("=== EXPERIENCE"):
                if current_block:
                    exp_blocks.append(current_block)
                current_block = {}
            elif s.startswith("Role:"):
                current_block["role"] = s[5:].strip()
            elif s.startswith("Company:"):
                current_block["company"] = s[8:].strip()
            elif s.startswith("Period:"):
                current_block["period"] = s[7:].strip()
            elif s.startswith("Description:"):
                current_block["desc"] = s[12:].strip()

        elif current_section == "proj":
            if s.startswith("=== PROJECT"):
                if current_block:
                    proj_blocks.append(current_block)
                current_block = {}
            elif s.startswith("Name:"):
                current_block["title"] = s[5:].strip()
            elif s.startswith("Technologies:"):
                current_block["tech"] = s[13:].strip()
            elif s.startswith("Description:"):
                current_block["desc"] = s[12:].strip()

        elif current_section == "edu":
            edu_lines.append(s.lstrip("- ").strip())

        elif current_section == "ach":
            ach_lines.append(s.lstrip("- ").strip())

    if current_block:
        if current_section == "exp":
            exp_blocks.append(current_block)
        elif current_section == "proj":
            proj_blocks.append(current_block)

    # ── Build skills MD ────────────────────────────────────────────────────
    skills_md = "## TECHNICAL SKILLS\n"
    for sk in skills_lines:
        skills_md += f"- {sk}\n"

    # ── Build experience MD ────────────────────────────────────────────────
    exp_md = "## WORK EXPERIENCE\n"
    for e in exp_blocks:
        role = e.get("role", "")
        company = e.get("company", "")
        period = e.get("period", "")
        desc = e.get("desc", "")

        heading = f"### {role}"
        if company:
            heading += f" @ {company}"
        if period:
            heading += f" | {period}"
        exp_md += heading + "\n"

        if desc:
            sentences = re.split(r"(?<=[.!?])\s+", desc)
            for sent in sentences[:3]:
                if sent.strip():
                    exp_md += f"- {sent.strip()}\n"
        else:
            exp_md += f"- Contributed to research and development initiatives at {company or 'this organization'}.\n"
        exp_md += "\n"

    # ── Build projects MD ──────────────────────────────────────────────────
    proj_md = "## PROJECTS\n"
    for p in proj_blocks:
        title = p.get("title", "Unnamed Project")
        tech = p.get("tech", "")
        desc = p.get("desc", "")

        proj_md += f"### {title}\n"
        if tech:
            proj_md += f"- **Tech Stack:** {tech}\n"
        if desc:
            sentences = re.split(r"(?<=[.!?])\s+", desc)
            for sent in sentences[:2]:
                if sent.strip():
                    proj_md += f"- {sent.strip()}\n"
        proj_md += "\n"

    # ── Build education MD ─────────────────────────────────────────────────
    edu_md = "## EDUCATION\n"
    for line in edu_lines:
        if line:
            edu_md += f"- {line}\n"

    # ── Build achievements MD ──────────────────────────────────────────────
    ach_md = ""
    if ach_lines:
        ach_md = "## ACHIEVEMENTS & CERTIFICATIONS\n"
        for line in ach_lines:
            if line:
                ach_md += f"- {line}\n"

    # ── Build summary ──────────────────────────────────────────────────────
    jd_words = set(re.findall(r"[A-Za-z]{4,}", jd_raw.lower())[:30])
    is_ai = bool(jd_words & {"machine", "learning", "llm", "model", "agent", "inference", "neural", "deep"})
    is_web = bool(jd_words & {"react", "frontend", "backend", "fullstack", "node", "typescript"})
    is_research = bool(jd_words & {"research", "publication", "paper", "lab", "analysis", "experiment"})

    if is_research:
        summary = (
            f"{name} is an AI/ML researcher with hands-on experience in deep learning model development, "
            f"medical imaging, and large-scale data pipelines. Track record of publishing research and "
            f"delivering measurable improvements in model performance across real-world applications."
        )
    elif is_ai:
        summary = (
            f"{name} is a results-driven AI/ML engineer with hands-on experience building and deploying "
            f"intelligent systems including LLMs, agentic architectures, and computer vision pipelines. "
            f"Proven ability to take models from research to production with measurable performance gains."
        )
    elif is_web:
        summary = (
            f"{name} is a full-stack engineer with expertise in modern web architectures, RESTful APIs, "
            f"and scalable backend systems. Proven ability to ship production-quality software with "
            f"strong focus on performance and user experience."
        )
    else:
        summary = (
            f"{name} is a technically skilled engineer with a track record of delivering impactful "
            f"solutions. Experienced in building ML systems, engineering data pipelines, and collaborating "
            f"on cross-functional projects with measurable outcomes."
        )

    resume = f"""# {name}

## PROFESSIONAL SUMMARY
{summary}

---

{skills_md}
---

{exp_md}
---

{proj_md}
---

{edu_md}
{ach_md}"""

    return _format_resume_structure(_post_process_resume(resume))


# ─────────────────────────────────────────────────────────────────────────────
# HuggingFace API caller
# ─────────────────────────────────────────────────────────────────────────────

_HF_MODELS_CACHE: dict[str, Any] = {"timestamp": 0.0, "candidates": []}
CACHE_TTL_SECONDS = 1800.0  # 30 minutes cache


def scrape_and_classify_hf_models() -> list[dict[str, Any]]:
    """Scrapes live models from https://huggingface.co/inference/models,

    classifies them by parameter size and capability, and returns an ordered
    list of candidate model dicts: [{"provider": ..., "model_id": ..., "score":
    ...}].
    """
    global _HF_MODELS_CACHE
    now = time.time()
    if now - _HF_MODELS_CACHE["timestamp"] < CACHE_TTL_SECONDS and _HF_MODELS_CACHE["candidates"]:
        return _HF_MODELS_CACHE["candidates"]

    url = "https://huggingface.co/inference/models"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    candidates = []
    seen_pairs = set()

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            for m in re.finditer(r"data-props=\"([^\"]+)\"", r.text):
                raw = html.unescape(m.group(1))
                try:
                    obj = json.loads(raw)
                    if isinstance(obj, dict) and "mappings" in obj:
                        for item in obj.get("mappings", []):
                            status = item.get("status")
                            prov = item.get("provider")
                            model_data = item.get("model", {})
                            model_id = model_data.get("id", "")

                            if status == "live" and prov and model_id:
                                pair_key = (prov, model_id)
                                if pair_key in seen_pairs:
                                    continue
                                seen_pairs.add(pair_key)

                                mid_lower = model_id.lower()
                                if any(
                                    x in mid_lower
                                    for x in [
                                        "embedding",
                                        "diffus",
                                        "vision",
                                        "whisper",
                                        "tts",
                                        "stt",
                                        "audio",
                                    ]
                                ):
                                    continue

                                score = 0
                                if any(x in mid_lower for x in ["235b", "141b", "120b", "80b", "72b", "70b"]):
                                    score += 50
                                elif any(x in mid_lower for x in ["35b", "33b", "32b", "27b", "8x7b"]):
                                    score += 35
                                elif any(x in mid_lower for x in ["14b", "11b", "9b", "8b", "7b"]):
                                    score += 20

                                if any(x in mid_lower for x in ["instruct", "chat", "it"]):
                                    score += 15

                                if prov in ["nscale", "together", "baseten", "groq", "hf-inference", "novita"]:
                                    score += 10

                                candidates.append({
                                    "provider": prov,
                                    "model_id": model_id,
                                    "score": score,
                                })
                except Exception:
                    pass
    except Exception as exc:
        logger.warning("Scraping HF inference models failed: %s", exc)

    default_fallbacks = [
        ("together", "meta-llama/Llama-3.3-70B-Instruct", 70),
        ("novita", "meta-llama/Llama-3.3-70B-Instruct", 70),
        ("nscale", "meta-llama/Llama-3.1-8B-Instruct", 40),
        ("hf-inference", "meta-llama/Llama-3.3-70B-Instruct", 60),
        ("hf-inference", "meta-llama/Llama-3.1-70B-Instruct", 55),
        ("hf-inference", "Qwen/Qwen2.5-72B-Instruct", 50),
        ("hf-inference", "mistralai/Mixtral-8x22B-Instruct-v0.1", 45),
        ("hf-inference", "meta-llama/Llama-3.1-8B-Instruct", 30),
        ("hf-inference", "mistralai/Mistral-7B-Instruct-v0.3", 25),
        ("hf-inference", "Qwen/Qwen2.5-7B-Instruct", 20),
    ]

    for prov, model_id, score in default_fallbacks:
        if (prov, model_id) not in seen_pairs:
            seen_pairs.add((prov, model_id))
            candidates.append({"provider": prov, "model_id": model_id, "score": score})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    _HF_MODELS_CACHE = {"timestamp": now, "candidates": candidates}
    return candidates


def call_huggingface(api_key: str, prompt: str, model: str | None = None) -> str:
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    system_message = (
        "You are an elite technical resume writer specializing in ATS-optimized, "
        "interview-winning resumes for software engineers and AI/ML practitioners. "
        "You always output ONLY the resume content in Markdown format — no preamble, "
        "no explanation, no 'Here is your resume', just the resume itself starting "
        "with the candidate's name as a # heading. "
        "CRITICAL: Never output 'N/A', emojis, or unicode symbols. "
        "Every bullet must start with an action verb and include a concrete metric or outcome."
    )

    candidates = scrape_and_classify_hf_models()

    attempts = []
    if model:
        attempts.append({"provider": "hf-inference", "model_id": model})
        attempts.append({"provider": None, "model_id": model})

    for cand in candidates:
        attempts.append(cand)
        attempts.append({"provider": None, "model_id": cand["model_id"]})

    seen_attempts = set()
    # Track whether every failure was a "permissions" error (HF Inference Provider access issue)
    _permissions_fail_count = 0
    _total_attempts = 0

    for item in attempts:
        prov = item.get("provider")
        m = item.get("model_id")
        if not m:
            continue

        key = (prov, m)
        if key in seen_attempts:
            continue
        seen_attempts.add(key)

        urls = []
        if prov:
            urls.append(f"https://router.huggingface.co/{prov}/v1/chat/completions")
        urls.append("https://router.huggingface.co/v1/chat/completions")
        urls.append("https://router.huggingface.co/hf-inference/v1/chat/completions")

        for chat_url in urls:
            logger.info("Attempting resume generation via URL: %s | Model: %s", chat_url, m)
            payload = {
                "model": m,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 3000,
                "temperature": 0.2,
            }
            try:
                _total_attempts += 1
                resp = requests.post(chat_url, headers=headers, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0].get("message", {}).get("content")
                        if content and content.strip():
                            logger.info("Resume generated successfully using model %s via %s", m, chat_url)
                            return _format_resume_structure(_post_process_resume(content.strip()))
                elif resp.status_code in (401, 403):
                    resp_text_lower = resp.text.lower()
                    # "sufficient permissions" / "Inference Providers" → HF token lacks provider access.
                    # This is a permanent account-level restriction — retrying more URL variants
                    # for this model will always fail. Skip to the next model immediately.
                    if "sufficient permissions" in resp_text_lower or "inference provider" in resp_text_lower:
                        _permissions_fail_count += 1
                        logger.warning(
                            "Model %s via %s: HF Inference Provider access denied (token lacks permissions). "
                            "Skipping remaining URL variants for this model.",
                            m, chat_url,
                        )
                        break  # skip remaining URL variants for this model
                    elif "invalid" in resp_text_lower or "token" in resp_text_lower:
                        raise HTTPException(
                            status_code=401,
                            detail=(
                                "Invalid Hugging Face API key. Please check your HF token "
                                "in settings (must be a valid token from huggingface.co/settings/tokens)."
                            ),
                        )
                    else:
                        logger.warning("Model %s via %s returned HTTP %s: %s", m, chat_url, resp.status_code, resp.text[:200])
                else:
                    logger.warning("Model %s via %s returned HTTP %s: %s", m, chat_url, resp.status_code, resp.text[:200])
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning("Model %s via %s raised exception: %s", m, chat_url, exc)

    # If every single attempt failed with an "Inference Provider permissions" error,
    # surface a clear, actionable message to the user instead of running the fallback silently.
    if _permissions_fail_count > 0 and _permissions_fail_count >= len(seen_attempts):
        logger.error(
            "All %d model attempts failed: HF token lacks Inference Provider permissions. "
            "Raising HTTP 403 to user.",
            _permissions_fail_count,
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Your Hugging Face token does not have access to Inference Providers. "
                "Please go to huggingface.co/settings/tokens, open your token, and enable "
                "'Make calls to Inference Providers' under the token permissions. "
                "Then update your token in Relexer settings."
            ),
        )

    # Structured fallback — all LLM calls failed for other reasons
    logger.error("ALL HuggingFace API calls failed. Running structured fallback.")
    return generate_structured_resume_fallback(prompt)


# ─────────────────────────────────────────────────────────────────────────────
# PDF renderer
# ─────────────────────────────────────────────────────────────────────────────

def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Word-wrap a single line into multiple lines of at most max_chars."""
    if not text:
        return [""]
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _strip_markdown_inline(text: str) -> str:
    """Strip **bold**, *italic*, backtick and heading markers for plain PDF rendering."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)         # italic
    text = re.sub(r"`([^`]*)`", r"\1", text)         # inline code
    text = re.sub(r"^#{1,6}\s*", "", text)            # heading markers
    # Strip remaining unicode symbols / emojis
    text = _strip_emojis(text)
    return text.strip()


def render_pdf(title: str, content: str) -> bytes:
    import re as _re

    # Pre-process content: strip emojis at PDF stage too
    content = _strip_emojis(content)

    buffer = BytesIO()
    doc = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin_left = 0.75 * inch
    margin_right = 0.75 * inch
    margin_top = 0.75 * inch
    margin_bottom = 0.75 * inch
    width - margin_left - margin_right
    max_chars_body = 95
    max_chars_bullet = 88

    # ─── Colors (Emerald palette) ───
    EMERALD    = (0.063, 0.725, 0.506)   # #10b981
    DARK_BLUE  = (0.059, 0.059, 0.220)   # near-black for name
    BODY_GRAY  = (0.17, 0.17, 0.17)      # body text
    LIGHT_GRAY = (0.45, 0.45, 0.45)      # meta / subtitle

    def set_color(rgb):
        doc.setFillColorRGB(*rgb)

    def draw_line(y_pos, color=EMERALD, width_pt=1.0):
        doc.setStrokeColorRGB(*color)
        doc.setLineWidth(width_pt)
        doc.line(margin_left, y_pos, width - margin_right, y_pos)

    def new_page():
        doc.showPage()
        return height - margin_top

    def check_page(y_pos, needed=0.25 * inch):
        if y_pos < margin_bottom + needed:
            return new_page()
        return y_pos

    y = height - margin_top

    # ─── Name Header ───
    candidate_name = title
    lines_iter = iter(content.splitlines())
    remaining_lines = []
    for raw in lines_iter:
        stripped = raw.strip()
        if stripped.startswith("# ") and candidate_name == title:
            candidate_name = stripped[2:].strip()
        elif stripped.startswith("# "):
            remaining_lines.append(raw)
        else:
            remaining_lines.append(raw)
            break
    remaining_lines.extend(lines_iter)

    doc.setFont("Helvetica-Bold", 22)
    set_color(DARK_BLUE)
    doc.drawString(margin_left, y, candidate_name)
    y -= 0.28 * inch
    draw_line(y, EMERALD, 2.0)
    y -= 0.18 * inch

    # ─── Render Body ───
    # Pre-normalise to ensure inline headers or horizontal rules are on separate lines
    content_to_render = _re.sub(r"\s*---+\s*", "\n---\n", content)
    content_to_render = _re.sub(r"(?<!\n)(#{1,4}\s+)", r"\n\1", content_to_render)

    lines_list = content_to_render.splitlines()
    # If first line was candidate name (# Name), skip it here as it was drawn in header
    if lines_list and lines_list[0].strip().startswith("# "):
        lines_list = lines_list[1:]

    for raw_line in lines_list:
        stripped = raw_line.strip()

        if not stripped:
            y -= 0.08 * inch
            y = check_page(y, 0.15 * inch)
            continue

        # H2 — Section heading
        if stripped.startswith("## "):
            y = check_page(y, 0.45 * inch)
            y -= 0.1 * inch
            heading_text = _strip_markdown_inline(stripped)
            doc.setFont("Helvetica-Bold", 11)
            set_color(EMERALD)
            doc.drawString(margin_left, y, heading_text.upper())
            y -= 0.16 * inch
            draw_line(y, EMERALD, 0.6)
            y -= 0.14 * inch
            doc.setFont("Helvetica", 10)
            set_color(BODY_GRAY)
            continue

        # H3 — Sub-heading (Role @ Company | Period)
        if stripped.startswith("### "):
            y = check_page(y, 0.30 * inch)
            subheading_text = _strip_markdown_inline(stripped)
            doc.setFont("Helvetica-Bold", 10)
            set_color(DARK_BLUE)
            wrapped = _wrap_text(subheading_text, max_chars_body)
            for wl in wrapped:
                y = check_page(y)
                doc.drawString(margin_left, y, wl)
                y -= 0.175 * inch
            doc.setFont("Helvetica", 10)
            set_color(BODY_GRAY)
            continue

        # H1 in body
        if stripped.startswith("# "):
            y = check_page(y, 0.30 * inch)
            text = _strip_markdown_inline(stripped)
            doc.setFont("Helvetica-Bold", 13)
            set_color(DARK_BLUE)
            for wl in _wrap_text(text, max_chars_body):
                y = check_page(y)
                doc.drawString(margin_left, y, wl)
                y -= 0.2 * inch
            doc.setFont("Helvetica", 10)
            set_color(BODY_GRAY)
            continue

        # Horizontal rule
        if _re.match(r"^-{3,}$", stripped):
            y -= 0.05 * inch
            draw_line(y, (0.8, 0.8, 0.8), 0.4)
            y -= 0.10 * inch
            continue

        # Bullet point
        if _re.match(r"^[-*•]\s+", stripped):
            bullet_text = _re.sub(r"^[-*•]\s+", "", stripped)
            bullet_text = _strip_markdown_inline(bullet_text)
            wrapped = _wrap_text(bullet_text, max_chars_bullet)
            for i, wl in enumerate(wrapped):
                y = check_page(y)
                doc.setFont("Helvetica", 10)
                set_color(BODY_GRAY)
                if i == 0:
                    set_color(BODY_GRAY)
                    doc.circle(margin_left + 0.18 * inch, y + 3.2, 1.8, fill=1, stroke=0)
                    doc.drawString(margin_left + 0.30 * inch, y, wl)
                else:
                    doc.drawString(margin_left + 0.30 * inch, y, wl)
                y -= 0.175 * inch
            continue

        # Contact / meta line (contains | separators)
        if "|" in stripped and not stripped.startswith("#"):
            clean = _strip_markdown_inline(stripped)
            doc.setFont("Helvetica", 9)
            set_color(LIGHT_GRAY)
            for wl in _wrap_text(clean, max_chars_body + 10):
                y = check_page(y)
                doc.drawString(margin_left, y, wl)
                y -= 0.16 * inch
            doc.setFont("Helvetica", 10)
            set_color(BODY_GRAY)
            continue

        # Regular paragraph
        clean = _strip_markdown_inline(stripped)
        doc.setFont("Helvetica", 10)
        set_color(BODY_GRAY)
        for wl in _wrap_text(clean, max_chars_body):
            y = check_page(y)
            doc.drawString(margin_left, y, wl)
            y -= 0.175 * inch

    doc.save()
    buffer.seek(0)
    return buffer.read()


def _wrap_line(text: str, max_chars: int) -> list[str]:
    """Legacy wrapper — delegates to _wrap_text."""
    return _wrap_text(text, max_chars)
