"""Cover letter builder.

Template mode works with no API key: it picks the internship that matches the JD
and cites the technologies the JD actually asks for. LLM mode, when configured,
rewrites the same facts into prose.
"""

from __future__ import annotations

import re

from . import config, db

GLOBAL_HINTS = ("united states", "usa", "u.s.", "europe", "uk", "london", "canada", "remote")
ENGLISH_SOURCES = {"greenhouse", "ashby", "lever", "workable", "remoteok"}


def _is_english(job: dict) -> bool:
    if job.get("source") in ENGLISH_SOURCES:
        return True
    location = (job.get("location") or "").lower()
    return any(hint in location for hint in GLOBAL_HINTS) and "indonesia" not in location


def _points(exp: dict) -> list[str]:
    """YAML can turn 'a: b' list items into dicts; flatten either shape to text."""
    out: list[str] = []
    for item in exp.get("poin") or []:
        if isinstance(item, dict):
            out.extend(f"{k}: {v}" for k, v in item.items())
        elif item:
            out.append(str(item))
    return out


def _pick_experience(job: dict, profile: dict) -> dict | None:
    jd = (job.get("description") or "").lower()
    if not jd:
        return (profile.get("pengalaman") or [None])[0]
    keywords = ("laravel", "react", "flutter", "api", "database", "support", "troubleshoot", "ai", "otomasi", "php")
    best, best_score = None, -1
    for exp in profile.get("pengalaman") or []:
        text = " ".join(_points(exp)).lower() + " " + (exp.get("posisi") or "").lower()
        score = sum(1 for kw in keywords if kw in text and kw in jd)
        if score > best_score:
            best, best_score = exp, score
    return best


def template_letter(job: dict, profile: dict, analysis: dict) -> str:
    english = _is_english(job)
    exp = _pick_experience(job, profile) or {}
    matched = []
    for strength in analysis.get("strengths") or []:
        if strength.startswith("skill cocok:"):
            matched = [s.strip() for s in strength.split(":", 1)[1].split(",")][:4]
    name = profile.get("nama", "Kevin Dwi Wijaya")
    company = job.get("company", "")
    title = job.get("title", "")
    portfolio = (profile.get("kontak") or {}).get("portfolio", "")
    degree = (profile.get("pendidikan") or [{}])[0]

    if english:
        lines = [
            f"Dear Hiring Team at {company},",
            "",
            f"I am writing to apply for the {title} position. I am a Diploma III graduate in "
            f"Management Informatics from Politeknik Negeri Malang and a full-stack developer "
            f"with internship experience building internal business systems.",
        ]
        if exp:
            lines += [
                "",
                f"As {exp.get('posisi')} at {exp.get('perusahaan')}, I worked on: "
                + "; ".join(_points(exp)[:2]).rstrip(".")
                + ".",
            ]
        if matched:
            lines += [
                "",
                f"The role's stack lines up with what I use daily: {', '.join(matched)}. "
                f"I have also earned the BNSP professional certification in Computer Software Programming.",
            ]
        gaps = [g for g in (analysis.get("gaps") or []) if "S1" in g or "tahun" in g]
        if gaps:
            lines += [
                "",
                "I want to be direct about one point: I hold a D3 rather than a bachelor's degree. "
                "What I lack in formal years I make up for in shipped work - five production "
                "applications during my internships, including an LMS, an internal marketplace, "
                "and a community governance platform.",
            ]
        lines += [
            "",
            f"My portfolio is at {portfolio}. I would welcome the chance to walk through the code "
            f"and discuss how I can contribute to your team.",
            "",
            "Sincerely,",
            name,
        ]
        return "\n".join(lines)

    lines = [
        f"Kepada Tim Rekrutmen {company},",
        "",
        f"Saya ingin melamar posisi {title}. Saya lulusan D3 Manajemen Informatika "
        f"Politeknik Negeri Malang (PSDKU Kediri) dengan pengalaman magang sebagai "
        f"full-stack developer dan IT support.",
    ]
    if exp:
        lines += [
            "",
            f"Selama menjadi {exp.get('posisi')} di {exp.get('perusahaan')}, saya mengerjakan: "
            + "; ".join(_points(exp)[:2]).rstrip(".")
            + ".",
        ]
    if matched:
        lines += [
            "",
            f"Stack yang dipakai di posisi ini sejalan dengan yang saya pakai sehari-hari: "
            f"{', '.join(matched)}. Saya juga memegang sertifikasi BNSP Pemrograman Software Komputer.",
        ]
    gaps = [g for g in (analysis.get("gaps") or []) if "S1" in g or "tahun" in g]
    if gaps:
        lines += [
            "",
            "Saya ingin jujur soal satu hal: ijazah saya D3, bukan S1. Sebagai gantinya, "
            "saya sudah mengerjakan lima aplikasi produksi selama magang - LMS, marketplace "
            "internal, sistem administrasi RT/RW, e-commerce farmasi, dan aplikasi keuangan.",
        ]
    lines += [
        "",
        f"Portofolio saya ada di {portfolio}. Saya terbuka untuk wawancara dan tes teknis "
        f"kapan pun dibutuhkan.",
        "",
        "Hormat saya,",
        f"{name} - {degree.get('kampus', 'Politeknik Negeri Malang')}",
    ]
    return "\n".join(lines)


LLM_PROMPT = """Tulis cover letter untuk lowongan berikut, dalam bahasa {language}.

KANDIDAT: {name}, lulusan D3 Manajemen Informatika Politeknik Negeri Malang, full-stack developer
(Laravel, React, PHP, MySQL) dengan 3 magang: Telkom Akses (IT support), Kalamaya (LMS + AI automation),
Nusatama (marketplace internal, sistem stok). Sertifikasi BNSP. Portofolio {portfolio}. Fresh graduate 2026.

LOWONGAN: {title} di {company} ({location})
DESKRIPSI: {jd}

HASIL ANALISIS (gap yang harus dijawab jujur): {gaps}

Aturan:
- 180-220 kata, maksimal 4 paragraf.
- Sebut 2-3 bukti konkret dari pengalaman kandidat yang relevan dengan JD.
- Jangan mengarang pengalaman atau gelar.
- Kalau ada gap (S1 vs D3, pengalaman kurang), jawab singkat dan percaya diri, jangan defensif.
- Tanpa placeholder seperti [nama] atau [perusahaan].
- Akhiri dengan nama kandidat.
"""


def llm_letter(job: dict, profile: dict, analysis: dict) -> str | None:
    env = config.env()
    key = (env.get("LLM_API_KEY") or "").strip()
    if not key:
        return None
    import requests

    base = (env.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = env.get("LLM_MODEL") or "gpt-4o-mini"
    prompt = LLM_PROMPT.format(
        language="Inggris" if _is_english(job) else "Indonesia",
        name=profile.get("nama", ""),
        portfolio=(profile.get("kontak") or {}).get("portfolio", ""),
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        jd=(job.get("description") or "")[:5000],
        gaps="; ".join(analysis.get("gaps") or []),
    )
    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.5},
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def build(job: dict, profile: dict, analysis: dict) -> tuple[str, str]:
    """Returns (letter_text, engine)."""
    text = llm_letter(job, profile, analysis)
    if text:
        return text, "llm"
    return template_letter(job, profile, analysis), "template"
