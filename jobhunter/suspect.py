"""Red flags for postings that are live but not what they claim to be.

A single flag is often innocent (a hospital files IT Support under Healthcare),
so a posting is hidden only when its flags weigh HIDE_AT or more. Asking the
applicant for money weighs that much on its own.
"""

from __future__ import annotations

import re

HIDE_AT = 2

TECH_TRACKS = {"fullstack", "it_support", "ai_junior"}
CREATIVE_TRACKS = {"marketing", "social_media", "graphic_design", "video_editor"}

# JobStreet classification (text before " | ") a real posting of that family is filed under.
TECH_HOMES = {"information & communication technology", "it and software", "science & technology"}
# Engineering is fine for tech roles unless the sub-classification is plainly physical.
PHYSICAL_ENGINEERING = re.compile(r"civil|structural|mining|mechanical|chemical|building|construction", re.I)
CREATIVE_FAR = {
    "accounting", "mining, resources & energy", "construction", "healthcare & medical",
    "engineering", "banking & financial services", "insurance & superannuation", "legal",
}

BAIT = re.compile(
    r"di atas ekspektasi|penghasilan tanpa batas|tanpa (?:tes|interview|wawancara)|langsung (?:kerja|diterima)"
    r"|modal (?:hp|handphone)|kerja (?:santai )?dari hp|bonus jutaan|komisi tanpa batas",
    re.I,
)
MONEY_ASK = re.compile(
    r"biaya (?:pendaftaran|administrasi|admin|pelatihan|training|seragam|medical|tiket|pemberkasan)"
    r"|(?:wajib|harus) (?:transfer|membayar|bayar)|uang (?:jaminan|deposit|pendaftaran)|deposit awal",
    re.I,
)
PRIVATE_CONTACT = re.compile(r"wa\.me/|t\.me/|telegram|(?:whatsapp|\bwa\b)\s*[:.]?\s*(?:\+?62|0)8\d{7,}", re.I)
NO_REQUIREMENTS = re.compile(r"(?:persyaratan|kualifikasi|requirements?)\s*[:\-]?\s*(?:tidak disebutkan|-|n/?a)\b", re.I)
# Only "PT": "CV" in an ad is far more often the applicant's CV ("kirim CV Anda").
COMPANY_NAME = re.compile(r"\bPT\.?\s+((?:[A-Z][\w&'.-]*\s?){1,5})")
LEGAL_FORM = re.compile(r"\b(?:pt|cv|tbk|persero|indonesia|group|grup)\b\.?", re.I)


def _core(name: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", LEGAL_FORM.sub(" ", name.lower()))
    return {w for w in words if len(w) > 2}


def _other_company(company: str, description: str) -> str:
    """Name of a different company the ad body is really about, if any."""
    own = _core(company)
    if not own or own & _core(description):
        return ""
    names = [m.strip() for m in COMPANY_NAME.findall(description)]
    return names[0] if names else ""


def flags(row: dict, track: str) -> list[tuple[int, str]]:
    """(weight, reason) for each red flag on a posting."""
    out: list[tuple[int, str]] = []
    description = row.get("description") or ""
    company = row.get("company") or ""

    if row.get("source") == "jobstreet":
        top, _, sub = (row.get("department") or "").partition("|")
        top = top.strip().lower()
        if track in TECH_TRACKS and top and top not in TECH_HOMES and not (
            top == "engineering" and not PHYSICAL_ENGINEERING.search(sub)
        ):
            out.append((1, f"kategori '{row['department']}' tidak cocok untuk {track}"))
        if track in CREATIVE_TRACKS and top in CREATIVE_FAR:
            out.append((1, f"kategori '{row['department']}' tidak cocok untuk {track}"))

    if description:
        other = _other_company(company, description)
        if other:
            out.append((1, f"deskripsi tentang perusahaan lain (PT {other})"))
        if NO_REQUIREMENTS.search(description):
            out.append((1, "persyaratan kosong"))
        bait = BAIT.search(description)
        if bait:
            out.append((1, f"umpan '{bait.group(0)}'"))
        money = MONEY_ASK.search(description)
        if money:
            out.append((2, f"minta uang '{money.group(0)}'"))
        if PRIVATE_CONTACT.search(description):
            out.append((1, "melamar lewat WA/Telegram pribadi"))
    return out


def verdict(row: dict, track: str) -> str:
    """Reason text when the posting should be hidden, else ''."""
    found = flags(row, track)
    if sum(weight for weight, _ in found) < HIDE_AT:
        return ""
    return "; ".join(reason for _, reason in found)
