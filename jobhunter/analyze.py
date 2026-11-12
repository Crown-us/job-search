"""Fit analysis: CV vs job description.

Two modes, same output shape:

  heuristic  — always available. Reads the JD for degree level, years required,
               fresh-graduate friendliness, and tech overlap with profile.yaml.
  llm        — when LLM_API_KEY is set. Same contract, sharper judgement.

Output: {"fit": 0-100, "verdict": str, "gaps": [...], "strengths": [...]}
"""

from __future__ import annotations

import json
import re

from . import config

# Technologies worth flagging when a JD asks for them and the CV lacks them.
TECH_VOCAB = {
    "php": ["php"],
    "laravel": ["laravel"],
    "react": ["react"],
    "vue": ["vue.js", "vuejs", "vue"],
    "angular": ["angular"],
    "next.js": ["next.js", "nextjs"],
    "node.js": ["node.js", "nodejs", "node "],
    "typescript": ["typescript"],
    "javascript": ["javascript"],
    "python": ["python"],
    "django": ["django"],
    "flask": ["flask"],
    "java": ["java"],
    "spring": ["spring boot", "spring"],
    ".net": [".net", "asp.net", "c#"],
    "go": ["golang", "go lang"],
    "ruby": ["ruby"],
    "flutter": ["flutter"],
    "kotlin": ["kotlin"],
    "swift": ["swift"],
    "mysql": ["mysql"],
    "postgresql": ["postgresql", "postgres"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git"],
    "linux": ["linux", "ubuntu", "debian"],
    "aws": ["aws", "amazon web services"],
    "gcp": ["gcp", "google cloud"],
    "azure": ["azure"],
    "ci/cd": ["ci/cd", "cicd", "jenkins", "github actions", "gitlab ci"],
    "rest api": ["rest api", "restful"],
    "graphql": ["graphql"],
    "tailwind": ["tailwind"],
    "excel": ["excel"],
    "sql": ["sql"],
    "unit testing": ["unit test", "phpunit", "jest", "pytest"],
    "agile": ["agile", "scrum"],
}

S1_RE = re.compile(r"\b(s1|sarjana|bachelor'?s?|bachelor)\b", re.I)
D3_RE = re.compile(r"\b(d3|d-3|d\.3|diploma|associate degree)\b", re.I)
_NOT_D3_RE = re.compile(r"high[- ]school diploma|diploma (?:sma|smk)|\bd3\.?js\b", re.I)
# Kata yang menandai S1 itu preferensi, bukan syarat mutlak.
SOFT_RE = re.compile(
    r"diutamakan|lebih disukai|disukai|nilai (?:plus|tambah|lebih)|tidak wajib|"
    r"preferred|preferably|preferable|nice to have|(?:a|is a|as a) (?:plus|bonus)|"
    r"not (?:required|mandatory)|optional",
    re.I,
)
# Pengalaman diterima sebagai pengganti gelar: selalu melunakkan S1 di kalimat itu.
ALT_RE = re.compile(
    r"or equivalent (?:\w+ )?experience|atau pengalaman (?:kerja )?(?:yang )?setara", re.I
)
# "D3" di kalimat begini adalah library D3.js, bukan ijazah.
_D3_LIBRARY_RE = re.compile(r"d3\.?js|visuali[sz]|chart|librar|svg|canvas|plotly", re.I)
_SEGMENT_RE = re.compile(r"[\n.;•]+")
# Setelah penanda, kalimat harus selesai; kalau lanjut ("diutamakan berpengalaman
# Laravel") berarti yang diutamakan hal lain, bukan gelarnya.
_SOFT_TAIL_RE = re.compile(r"\s*(?:[),:]|$|but\b|namun\b|tapi\b|tetapi\b)", re.I)

GAP_S1 = "minta S1/sarjana, CV lo D3"
GAP_S1_SOFT = "S1 diutamakan (bukan wajib), CV lo D3"


def _s1_is_soft(segment: str, s1: re.Match[str]) -> bool:
    if ALT_RE.search(segment, s1.end()):
        return True
    for soft in SOFT_RE.finditer(segment):
        if soft.end() <= s1.start():
            between = segment[soft.end():s1.start()]
            if len(between) <= 40 and "," not in between:
                return True
        elif soft.start() >= s1.end():
            between = segment[s1.end():soft.start()]
            # Koma atau isi kurung di antaranya berarti yang diutamakan hal lain
            # ("S1, jurusan marketing preferred", "S1 (Sastra Cina preferred)").
            aside = between[between.rfind("(") + 1:].strip() if "(" in between else ""
            if (len(between) <= 60 and "," not in between and not aside
                    and _SOFT_TAIL_RE.match(segment, soft.end())):
                return True
    return False


def _mentions_d3(text: str) -> bool:
    for segment in _SEGMENT_RE.split(text):
        for hit in D3_RE.finditer(segment):
            if hit.group(1).lower() != "d3" or not _D3_LIBRARY_RE.search(segment):
                return True
    return False


def degree_requirement(jd: str) -> str:
    """Seberapa keras JD meminta gelar: 'd3_ok', 'required', 'preferred', atau ''.

    D3 yang disebut di mana pun ("D3/S1", "minimal D3") menang: lowongan itu
    terbuka untuk D3. Tanpa itu, S1 dianggap wajib kecuali setiap penyebutannya
    diberi penanda preferensi.
    """
    text = _NOT_D3_RE.sub(" ", jd)
    if _mentions_d3(text):
        return "d3_ok"
    found = False
    for segment in _SEGMENT_RE.split(text):
        for s1 in S1_RE.finditer(segment):
            found = True
            if not _s1_is_soft(segment, s1):
                return "required"
    return "preferred" if found else ""
FRESH_RE = re.compile(r"fresh graduate|freshgrad|lulusan baru|open to fresh|new grad", re.I)
YEARS_RE = re.compile(
    r"(?:min(?:imum|imal)?|at least|paling sedikit|min\.)\s*(\d+)\s*\+?\s*(?:year|tahun|thn)", re.I
)
ENGLISH_RE = re.compile(r"\b(english|bahasa inggris|inggris)\b", re.I)


def _profile_tokens(profile: dict) -> set[str]:
    """Flatten every skill into lowercase tokens: 'Microsoft Excel' -> {microsoft, excel}."""
    tokens: set[str] = set()
    for values in (profile.get("skill") or {}).values():
        for value in values or []:
            text = re.sub(r"\(.*?\)", "", str(value)).lower()
            tokens.update(re.findall(r"[a-z0-9+#.]+", text))
    return tokens


def _alias_pattern(alias: str) -> re.Pattern[str]:
    # Word-ish boundaries that also work for 'c#', '.net' and 'node.js'.
    return re.compile(r"(?<![\w+#.])" + re.escape(alias.strip()) + r"(?![\w+#])", re.I)


_PATTERNS = {
    canonical: [_alias_pattern(a) for a in aliases] for canonical, aliases in TECH_VOCAB.items()
}


def _jd_tech(jd: str) -> set[str]:
    found = set()
    for canonical, patterns in _PATTERNS.items():
        if any(p.search(jd) for p in patterns):
            found.add(canonical)
    return found


def _match_skill(canonical: str, tokens: set[str]) -> bool:
    """'microsoft excel' contains token 'excel'; 'javascript' does not contain 'java'."""
    if canonical in tokens:
        return True
    parts = canonical.replace("/", " ").split()
    return bool(parts) and all(part in tokens for part in parts)


def heuristic_analysis(job: dict, profile: dict) -> dict:
    jd = (job.get("description") or "").strip()
    gaps: list[str] = []
    strengths: list[str] = []

    if len(jd) < 120:
        return {
            "fit": job.get("score") or 50,
            "verdict": "JD terlalu pendek untuk dianalisis",
            "gaps": ["JD tidak tersedia — jalankan `enrich` dulu"],
            "strengths": [],
        }

    months = int(profile.get("pengalaman_total_bulan") or 0)
    years_have = months / 12

    degree = degree_requirement(jd)
    if degree == "required":
        gaps.append(GAP_S1)
    elif degree == "preferred":
        gaps.append(GAP_S1_SOFT)
    elif degree == "d3_ok":
        strengths.append("D3 diterima/disebut eksplisit")

    if FRESH_RE.search(jd):
        strengths.append("fresh graduate dipersilakan")

    match_years = YEARS_RE.search(jd)
    if match_years:
        required = int(match_years.group(1))
        if required > years_have:
            gaps.append(f"minta min. {required} tahun, lo ~{years_have:.1f} tahun (magang)")
        else:
            strengths.append(f"pengalaman cukup ({years_have:.1f} th vs minta {required})")

    jd_tech = _jd_tech(jd)
    have = _profile_tokens(profile)
    matched = sorted(t for t in jd_tech if _match_skill(t, have))
    missing = sorted(t for t in jd_tech if not _match_skill(t, have))

    if matched:
        strengths.append("skill cocok: " + ", ".join(matched[:6]))
    if missing:
        gaps.append("belum di CV: " + ", ".join(missing[:6]))

    if ENGLISH_RE.search(jd):
        strengths.append("Inggris disebut — CV lo profesional")

    overlap = len(matched) / max(1, len(jd_tech))
    tech_score = 100 * overlap if jd_tech else 55
    base = job.get("score") or 50
    fit = round(0.55 * base + 0.45 * tech_score)
    fit -= 10 * gaps.count(GAP_S1)
    fit -= 3 * gaps.count(GAP_S1_SOFT)
    fit -= 6 * sum(1 for g in gaps if g.startswith("minta min."))
    fit = max(0, min(100, fit))

    if fit >= 75:
        verdict = "layak dikejar"
    elif fit >= 60:
        verdict = "worth a shot, tapi ada gap"
    elif fit >= 45:
        verdict = "gap cukup besar"
    else:
        verdict = "skip"

    return {"fit": fit, "verdict": verdict, "gaps": gaps, "strengths": strengths}


PROMPT = """Kamu asisten karier yang jujur dan to the point.

PROFIL KANDIDAT (JSON):
{profile}

LOWONGAN:
Judul: {title}
Perusahaan: {company}
Lokasi: {location}
Deskripsi:
{jd}

Nilai kecocokan 0-100 dan kembalikan HANYA JSON valid dengan bentuk:
{{"fit": <int>, "verdict": "<satu kalimat>", "gaps": ["<gap konkret>"], "strengths": ["<kekuatan konkret>"], "advice": "<saran 1-2 kalimat>"}}

Aturan:
- Bandingkan requirement di JD dengan fakta di profil. Jangan mengarang pengalaman.
- Kalau JD minta S1 dan kandidat D3, itu gap, tapi sebut kalau fresh graduate dipersilakan.
- Bedakan S1 wajib dari S1 "diutamakan/preferred": yang kedua gap kecil. "D3/S1" atau "minimal D3" bukan gap.
- Kalau JD minta pengalaman bertahun-tahun dan kandidat cuma magang, itu gap besar.
- gaps maksimal 5, strengths maksimal 5, bahasa Indonesia, spesifik (sebut teknologi/angka).
"""


def has_llm() -> bool:
    return bool((config.env().get("LLM_API_KEY") or "").strip())


def llm_analysis(job: dict, profile: dict) -> dict | None:
    env = config.env()
    key = (env.get("LLM_API_KEY") or "").strip()
    if not key:
        return None
    base = (env.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = env.get("LLM_MODEL") or "gpt-4o-mini"

    import requests

    prompt = PROMPT.format(
        profile=json.dumps(profile, ensure_ascii=False)[:3000],
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        jd=(job.get("description") or "")[:6000],
    )
    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        return {
            "fit": int(data.get("fit", 0)),
            "verdict": data.get("verdict", ""),
            "gaps": list(data.get("gaps") or [])[:6],
            "strengths": list(data.get("strengths") or [])[:6],
            "advice": data.get("advice", ""),
        }
    except Exception as exc:
        return {
            "fit": 0,
            "verdict": f"LLM gagal: {type(exc).__name__}",
            "gaps": [str(exc)[:120]],
            "strengths": [],
        }


def analyze(job: dict, profile: dict) -> dict:
    result = llm_analysis(job, profile)
    if result is None:
        result = heuristic_analysis(job, profile)
        result["engine"] = "heuristic"
    else:
        result["engine"] = "llm"
    return result
