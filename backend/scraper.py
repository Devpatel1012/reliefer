import base64
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

logger = logging.getLogger("reliefer.scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Extended tech keyword regex covering 50+ technologies
TECH_KEYWORDS_RE = re.compile(
    r'\b('
    r'Python|JavaScript|TypeScript|React|FastAPI|Node\.js|NodeJS|'
    r'TensorFlow|PyTorch|LangChain|Docker|Kubernetes|PostgreSQL|'
    r'MongoDB|Redis|Rust|Go|Java|C\+\+|CUDA|Cuda|HuggingFace|'
    r'Transformers|OpenAI|Streamlit|Flask|Django|Vue|Angular|'
    r'Next\.js|NextJS|GraphQL|REST|AWS|GCP|Azure|Spark|Kafka|'
    r'Scikit-learn|sklearn|Pandas|NumPy|Matplotlib|OpenCV|Keras|'
    r'Tailwind|Bootstrap|Svelte|SvelteKit|Prisma|'
    r'Elasticsearch|MySQL|SQLite|Firebase|Supabase|'
    r'Linux|Bash|Shell|Git|Jupyter|Colab|LLM|RAG|ONNX'
    r')\b',
    re.IGNORECASE
)


def _get_gh_api_headers() -> dict[str, str]:
    headers = {
        "User-Agent": "Reliefer/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _clean_readme_markdown(text: str) -> str:
    """Strip markdown syntax for clean plain text."""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    text = re.sub(r">\s*", "", text)
    text = re.sub(r"[-*+]\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:800]


def _fetch_readme(username: str, repo_name: str) -> str:
    """Fetch and decode a README. Tries raw CDN first (no API cost), then REST API."""
    for branch in ["main", "master"]:
        raw_url = f"https://raw.githubusercontent.com/{username}/{repo_name}/{branch}/README.md"
        try:
            resp = requests.get(raw_url, headers=HEADERS, timeout=5)
            if resp.status_code == 200 and resp.text.strip():
                return _clean_readme_markdown(resp.text)
        except Exception:
            pass

    readme_url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
    try:
        resp = requests.get(readme_url, headers=_get_gh_api_headers(), timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            encoded = data.get("content", "")
            if encoded:
                decoded = base64.b64decode(encoded.replace("\n", "")).decode("utf-8", errors="ignore")
                return _clean_readme_markdown(decoded)
    except Exception:
        pass

    return ""


def _fetch_readme_parallel(username: str, repos: list[dict], max_workers: int = 10) -> dict[str, str]:
    """Fetch READMEs for multiple repos in parallel. Returns {repo_name: readme_text}."""
    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_name = {
            executor.submit(_fetch_readme, username, repo["name"]): repo["name"]
            for repo in repos
        }
        try:
            for future in as_completed(future_to_name, timeout=25):
                repo_name = future_to_name[future]
                try:
                    results[repo_name] = future.result(timeout=5)
                except Exception:
                    results[repo_name] = ""
        except Exception:
            # Timeout or cancellation — collect whatever we have so far
            for name in future_to_name.values():
                if name not in results:
                    results[name] = ""
    return results


def _build_project_description(repo: dict, readme_text: str) -> str:
    """Build best possible project description from available data."""
    repo_name = repo.get("name", "Project")
    stars = repo.get("stargazers_count", 0)

    if readme_text and len(readme_text) > 60:
        sentences = re.split(r'(?<=[.!?])\s+', readme_text)
        summary = ""
        for s in sentences:
            if len(s.strip()) > 20:
                summary += s.strip() + " "
            if len(summary) >= 180:
                break
        if summary.strip():
            suffix = f" | {stars} ⭐" if stars > 0 else ""
            return summary.strip()[:250] + suffix

    if repo.get("description"):
        suffix = f" ({stars} ⭐)" if stars > 0 else ""
        return repo["description"].strip()[:200] + suffix

    readable = repo_name.replace("-", " ").replace("_", " ").title()
    lang = repo.get("language") or ""
    tech_hint = f" built with {lang}" if lang else ""
    return f"{readable}{tech_hint} — open source project."


def _repo_quality_score(repo: dict, has_readme: bool) -> int:
    """Score a repo for relevance/quality."""
    score = 0
    score += min(repo.get("stargazers_count", 0) * 5, 50)
    score += min(repo.get("forks_count", 0) * 2, 20)
    score += 20 if has_readme else 0
    score += 15 if repo.get("description") else 0
    score += 10 if repo.get("language") else 0
    score -= 30 if repo.get("fork") else 0
    score -= 20 if repo.get("archived") else 0

    name_lower = repo.get("name", "").lower()
    if re.match(r"^\w+\.github\.io$", name_lower):
        score -= 15  # GitHub Pages personal site
    elif re.match(r"^leetcode", name_lower):
        score -= 15  # LeetCode dump
    elif re.match(r"^hello.world", name_lower):
        score -= 15

    return score


def _extract_skills_from_readme(readme_text: str, lang: str | None = None) -> list[str]:
    """Extract tech skills mentioned in README text."""
    skills = []
    if lang:
        skills.append(lang)
    if readme_text:
        found = TECH_KEYWORDS_RE.findall(readme_text)
        seen = {s.lower() for s in skills}
        for tech in found:
            if tech.lower() not in seen:
                seen.add(tech.lower())
                skills.append(tech)
    return skills


def _infer_tech_from_readme(readme_text: str) -> str:
    """Infer tech stack from README text if no primary language is detected."""
    if not readme_text:
        return "Open Source"
    techs = TECH_KEYWORDS_RE.findall(readme_text)
    if techs:
        seen, unique = set(), []
        for t in techs:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
        return ", ".join(unique[:4])
    return "Open Source"


def _process_repos(username: str, candidate_repos: list[dict]) -> tuple:
    """
    Fetch READMEs in parallel, score repos, build descriptions.
    Returns (scored_repos_list, extracted_skills_set).
    """
    if not candidate_repos:
        return [], set()

    logger.info(f"Fetching READMEs for {len(candidate_repos)} repos in parallel for @{username}...")
    readme_map = _fetch_readme_parallel(username, candidate_repos, max_workers=10)

    extracted_skills: set = set()
    scored_repos: list[dict] = []

    for repo in candidate_repos:
        lang = repo.get("language")
        if lang:
            extracted_skills.add(lang)

        readme_text = readme_map.get(repo.get("name", ""), "")
        score = _repo_quality_score(repo, bool(readme_text))
        description = _build_project_description(repo, readme_text)

        if readme_text:
            for tech in _extract_skills_from_readme(readme_text, lang):
                extracted_skills.add(tech)

        scored_repos.append({
            "_score": score,
            "title": repo.get("name", "Project"),
            "description": description,
            "tech_stack": lang or _infer_tech_from_readme(readme_text),
            "link": repo.get("html_url", ""),
            "start_date": (repo.get("created_at") or "")[:7],
            "end_date": "Present" if not repo.get("archived") else (repo.get("updated_at") or "")[:7],
        })

    scored_repos.sort(key=lambda r: r["_score"], reverse=True)
    return scored_repos, extracted_skills


def _scrape_github_html_fallback(clean_user: str) -> dict[str, Any]:
    """Fallback HTML scraper for when GitHub API rate limit (403) is hit."""
    from bs4 import BeautifulSoup
    logger.info(f"Using HTML scraping fallback for GitHub user '{clean_user}'")
    user_page_url = f"https://github.com/{clean_user}"
    repos_page_url = f"https://github.com/{clean_user}?tab=repositories"

    user_data = {"name": clean_user, "bio": "", "company": "", "location": "", "avatar_url": ""}

    try:
        u_resp = requests.get(user_page_url, headers=HEADERS, timeout=8)
        if u_resp.status_code == 404:
            raise ValueError(f"GitHub user '{clean_user}' not found.")
        if u_resp.status_code == 200:
            u_soup = BeautifulSoup(u_resp.text, "html.parser")
            name_el = u_soup.find("span", class_="p-name")
            if name_el and name_el.text.strip():
                user_data["name"] = name_el.text.strip()
            bio_el = u_soup.find("div", class_="p-note")
            if bio_el and bio_el.text.strip():
                user_data["bio"] = bio_el.text.strip()
            org_el = u_soup.find("span", class_="p-org")
            if org_el and org_el.text.strip():
                user_data["company"] = org_el.text.strip()
            loc_el = u_soup.find("span", class_="p-label")
            if loc_el and loc_el.text.strip():
                user_data["location"] = loc_el.text.strip()
            avatar_el = u_soup.find("img", class_="avatar-user")
            if avatar_el and avatar_el.get("src"):
                user_data["avatar_url"] = avatar_el["src"]
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"Failed to scrape profile HTML for {clean_user}: {e}")

    all_repos = []
    try:
        r_resp = requests.get(repos_page_url, headers=HEADERS, timeout=8)
        if r_resp.status_code == 200:
            r_soup = BeautifulSoup(r_resp.text, "html.parser")
            repo_items = r_soup.find_all("li", class_="col-12")
            for item in repo_items:
                a_tag = item.find("a", itemprop="name codeRepository")
                if not a_tag:
                    continue
                repo_name = a_tag.text.strip()
                href = a_tag.get("href", "")
                full_link = f"https://github.com{href}" if href.startswith("/") else href
                desc_el = item.find("p", itemprop="description")
                desc = desc_el.text.strip() if desc_el else ""
                lang_el = item.find("span", itemprop="programmingLanguage")
                lang = lang_el.text.strip() if lang_el else ""
                all_repos.append({
                    "name": repo_name,
                    "description": desc,
                    "language": lang,
                    "html_url": full_link,
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "fork": False,
                    "archived": False,
                })
    except Exception as e:
        logger.warning(f"Failed to scrape repos HTML for {clean_user}: {e}")

    candidate_repos = [r for r in all_repos if not r.get("fork")]
    scored_repos, extracted_skills = _process_repos(clean_user, candidate_repos)
    top_repos = [{k: v for k, v in r.items() if k != "_score"} for r in scored_repos[:8]]

    experience_list = []
    if user_data.get("company"):
        experience_list.append({
            "role": "Software Developer",
            "company": user_data["company"].strip("@").strip(),
            "dates": "Present",
            "description": user_data.get("bio") or "Software Engineer",
        })

    return {
        "skills": sorted(extracted_skills),
        "projects": top_repos,
        "experience": experience_list,
        "education": [],
        "profile_info": user_data,
    }


def scrape_github_profile(username_or_url: str) -> dict[str, Any]:
    """Fetch a GitHub profile and extract rich project data using parallel README fetching.

    Fetches READMEs for all non-forked repos simultaneously (ThreadPoolExecutor, 10 workers),
    completing in ~5-8 seconds instead of 60+ seconds with sequential fetching.
    Falls back to HTML scraping if GitHub API rate limit (403) is hit.
    """
    clean_user = username_or_url.strip().rstrip("/")
    if "github.com/" in clean_user:
        clean_user = clean_user.split("github.com/")[-1].split("/")[0]

    clean_user = re.sub(r"[^\w\-]", "", clean_user)
    if not clean_user:
        raise ValueError("Invalid GitHub username provided.")

    gh_headers = _get_gh_api_headers()
    user_url = f"https://api.github.com/users/{clean_user}"
    repos_url = (
        f"https://api.github.com/users/{clean_user}/repos"
        f"?sort=updated&per_page=50&type=owner"
    )

    try:
        user_resp = requests.get(user_url, headers=gh_headers, timeout=10)
        if user_resp.status_code == 404:
            raise ValueError(f"GitHub user '{clean_user}' not found.")
        if user_resp.status_code == 403:
            return _scrape_github_html_fallback(clean_user)
        user_resp.raise_for_status()
        user_data = user_resp.json()

        repos_resp = requests.get(repos_url, headers=gh_headers, timeout=10)
        if repos_resp.status_code == 403:
            return _scrape_github_html_fallback(clean_user)

        all_repos = repos_resp.json() if repos_resp.status_code == 200 else []
        if not isinstance(all_repos, list):
            all_repos = []

        # Filter: only non-forked repos owned by this user
        candidate_repos = [r for r in all_repos if isinstance(r, dict) and not r.get("fork")]
        logger.info(f"Processing {len(candidate_repos)} repos for @{clean_user}")

        scored_repos, extracted_skills = _process_repos(clean_user, candidate_repos)
        top_repos = [{k: v for k, v in r.items() if k != "_score"} for r in scored_repos[:8]]

        experience_list = []
        if user_data.get("company"):
            company = user_data.get("company", "").strip("@").strip()
            experience_list.append({
                "role": "Software Developer",
                "company": company,
                "dates": "Present",
                "description": user_data.get("bio") or "Software Engineer",
            })

        return {
            "skills": sorted(extracted_skills),
            "projects": top_repos,
            "experience": experience_list,
            "education": [],
            "profile_info": {
                "name": user_data.get("name") or clean_user,
                "bio": user_data.get("bio") or "",
                "company": user_data.get("company") or "",
                "location": user_data.get("location") or "",
                "avatar_url": user_data.get("avatar_url") or "",
            },
        }

    except ValueError:
        raise
    except requests.RequestException as e:
        resp_status = getattr(getattr(e, "response", None), "status_code", None)
        if resp_status == 403 or "rate limit" in str(e).lower():
            return _scrape_github_html_fallback(clean_user)
        logger.error(f"Error calling GitHub API for '{clean_user}': {e}")
        raise RuntimeError(f"Failed to fetch GitHub profile for '{clean_user}'. Error: {e}")


def scrape_linkedin_profile(url_or_username: str) -> dict[str, Any]:
    """Scrape public LinkedIn profile data or parse raw profile text.
    Extracts Skills, Experience, Education, Projects, and Certifications.
    """
    from bs4 import BeautifulSoup
    from resume_parser import parse_resume_text_to_json

    raw_input = url_or_username.strip()
    if not raw_input:
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "projects": [],
            "achievements": [],
            "warning": "No LinkedIn profile URL or text provided.",
        }

    # If raw input contains multiple lines or section titles (Education, Projects, Certifications, etc.),
    # parse it directly as a raw profile text block.
    if "\n" in raw_input or any(kw in raw_input for kw in ["Education", "Projects", "Certifications", "Licenses", "Skills", "Experience"]):
        parsed = parse_resume_text_to_json(raw_input)
        return {
            "skills": parsed.get("skills", []),
            "experience": parsed.get("experience", []),
            "education": parsed.get("education", []),
            "projects": parsed.get("projects", []),
            "achievements": parsed.get("achievements", []),
            "profile_info": {
                "name": "LinkedIn User Profile",
                "headline": "Parsed Profile Data",
                "url": "",
            },
        }

    # Otherwise treat as URL or username
    if not raw_input.startswith("http"):
        if "linkedin.com/in/" in raw_input:
            target_url = f"https://{raw_input}"
        else:
            clean_username = re.sub(r"[^\w\-]", "", raw_input)
            target_url = f"https://www.linkedin.com/in/{clean_username}/"
    else:
        target_url = raw_input

    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(target_url, headers=browser_headers, timeout=8)
        if resp.status_code != 200:
            logger.warning(f"LinkedIn returned HTTP {resp.status_code} for {target_url}")
            return {
                "skills": [],
                "experience": [],
                "education": [],
                "projects": [],
                "achievements": [],
                "warning": (
                    f"LinkedIn restricts direct web scraping (HTTP {resp.status_code}). "
                    "Please paste your LinkedIn profile text or import your resume below to populate all sections instantly!"
                ),
                "can_paste": True,
            }

        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect page text from OpenGraph, JSON-LD, and meta tags
        extracted_text_blocks = []

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            extracted_text_blocks.append(og_title["content"])

        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            extracted_text_blocks.append(og_desc["content"])

        # Parse JSON-LD structured data if available
        ld_scripts = soup.find_all("script", type="application/ld+json")
        for sc in ld_scripts:
            if sc.string:
                extracted_text_blocks.append(sc.string)

        # Collect text from standard page elements
        for tag in soup.find_all(["p", "span", "h1", "h2", "h3", "li"]):
            txt = tag.get_text().strip()
            if len(txt) > 10:
                extracted_text_blocks.append(txt)

        aggregated_text = "\n".join(extracted_text_blocks)
        parsed = parse_resume_text_to_json(aggregated_text)

        name = ""
        if og_title and og_title.get("content"):
            title_text = og_title["content"]
            name = title_text.split("-")[0].strip() if "-" in title_text else title_text

        headline = og_desc["content"] if og_desc and og_desc.get("content") else ""

        return {
            "skills": parsed.get("skills", []),
            "experience": parsed.get("experience", []),
            "education": parsed.get("education", []),
            "projects": parsed.get("projects", []),
            "achievements": parsed.get("achievements", []),
            "profile_info": {
                "name": name or "LinkedIn User",
                "headline": headline,
                "url": target_url,
            },
        }

    except Exception as e:
        logger.error(f"Error scraping LinkedIn URL '{target_url}': {e}")
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "projects": [],
            "achievements": [],
            "warning": f"Unable to fetch profile automatically. Error: {e!s}. You can paste your profile text directly to extract all sections.",
            "can_paste": True,
        }
