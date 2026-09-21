#!/usr/bin/env python3
"""
ats_check.py - A lightweight Applicant Tracking System (ATS) simulator.

Parses resume files the way a real ATS would and reports what breaks:
  * PDF  -> text extraction via `pdftotext` (Xpdf/Poppler), reading-order + layout modes
  * DOCX -> native `word/document.xml` parse (this is literally how most ATS read .docx)

Checks performed per file:
  1. Extraction / parseability (is there a real text layer, or a scanned image?)
  2. Contact block (single consistent email, phone, LinkedIn, name at top)
  3. Section-heading recognition (standard ATS-mappable headings)
  4. Work-history reconstruction (title @ company + date range), order/overlap/gap analysis
  5. Column / table / text-box risk (content ATS commonly drops or scrambles)
  6. Keyword coverage against a role profile (and, with --jd, against a real job posting)
  7. Formatting hygiene (soft hyphens, ligatures, zero-width chars, exotic bullets)
  8. Document metadata & leftovers (stale titles, author fields, tracked changes,
     comments still embedded in a DOCX)
  9. Listing fitness (with --jd): scam / ghost-job trust signals in the posting text

Then a cross-file consistency pass (same email/phone/name/dates across every file).

Usage:
    py ats_check.py [PATH ...]            # files and/or directories (default: current dir)
    py ats_check.py --jd posting.txt      # score files against a posting + vet the posting
    py ats_check.py --gap postings/       # rank most-demanded terms across saved postings
    py ats_check.py --tracker tracker.csv # tracker analytics + follow-up dues
    py ats_check.py --check-links [...]   # fetch URLs found in the resumes, flag dead ones
    py ats_check.py --keywords terms.txt  # replace the built-in keyword profile
    py ats_check.py --json report.json    # also dump machine-readable results

No third-party packages required. Needs `pdftotext` on PATH for PDF files.
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# "Today" for open-ended ("Present") roles.
_now = datetime.date.today()
TODAY = (_now.year, _now.month)

DEFAULT_DIR = "."  # scan the current directory unless paths are given

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
MONTH_RE = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
# "Mon YYYY - Mon YYYY" or "Mon YYYY - Present" (various dashes)
DATE_RANGE_RE = re.compile(
    rf"({MONTH_RE})\.?\s+(\d{{4}})\s*[-–—to]+\s*"
    rf"(Present|Current|(?:{MONTH_RE})\.?\s+\d{{4}})",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().\-]{7,}\d)")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[A-Za-z0-9\-_/]+", re.IGNORECASE)

# Standard headings an ATS maps to structured fields, with accepted synonyms.
STANDARD_SECTIONS = {
    "summary": ["summary", "profile", "about", "objective"],
    "experience": ["experience", "professional experience", "employment",
                   "work history", "work experience", "professional experience continued"],
    "education": ["education", "education and selected professional development"],
    "skills": ["skills", "core skills", "core capabilities", "core competencies",
               "technical skills", "competencies", "key skills"],
    "certifications": ["certifications", "professional development",
                       "selected professional development", "licenses"],
    "languages": ["languages"],
}

# Default keyword profile (example: IT Operations / Endpoint / Identity / ITSM / Security).
# Field-specific -- replace it for your own domain via --keywords <file>, one term per line.
KEYWORDS = [
    "IT operations", "endpoint", "Intune", "Entra ID", "Autopilot", "Jamf", "macOS",
    "Active Directory", "ServiceNow", "BMC Helix", "ISO 27001", "vulnerability",
    "patch management", "identity and access", "IAM", "onboarding", "offboarding",
    "SOP", "KPI", "migration", "ITSM", "IT service management", "service delivery",
    "compliance", "security", "stakeholder", "acquisition", "endpoint security",
]

BULLET_CHARS = "•◦▪‣·-–—*"

# Document titles that scream "recycled file": what recruiters see in the tab bar.
JUNK_TITLE = re.compile(r"microsoft word|template|draft|copy of|untitled|\bv\d",
                        re.IGNORECASE)

# Characters that routinely corrupt ATS text extraction.
HOSTILE_CHARS = {
    "­": "soft hyphen (splits words)",
    "​": "zero-width space",
    "‌": "zero-width non-joiner",
    "﻿": "byte-order mark",
    "ﬁ": "ligature fi",
    "ﬂ": "ligature fl",
    "ﬀ": "ligature ff",
}

# Words too generic to count as job-description keywords.
JD_STOPWORDS = set("""
the a an and or of to in for with on at by from as is are was were be been being have has had
do does did will would can could should may might must shall not no nor but if then than so
such this that these those there here it its we you your our their they them about into over
under between across per via more most other others any all each both few new one two who
role job position candidate applicant company team teams work working environment culture
experience experiences years responsibilities responsibility requirements required requirement
preferred qualifications qualification skills skill ability able strong excellent good great
knowledge understanding familiarity proficiency plus bonus nice benefits salary equal
opportunity employer diversity location apply application day days including include includes
etc help ensure ensuring support supporting provide providing manage managing management
maintain maintaining develop developing development deliver delivering delivery lead leading
within without using use used level levels related relevant join what when where why how
looking seek seeking ideal successful duties description offer opportunities grow growth
own drive build create run report track hands hands-on 500 100 plus years mentor
""".split())


def extract_jd_terms(jd_text: str, top_n: int = 30) -> list[tuple[str, int]]:
    """Most salient single words and repeated bigrams from a job posting, by frequency."""
    words = [w.rstrip("./&-+#,") for w in
             re.findall(r"[a-z0-9][a-z0-9+#./&-]{2,}", jd_text.lower())]
    words = [w for w in words if len(w) >= 3]
    freq: dict[str, int] = {}
    for w in words:
        if w not in JD_STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    bigrams: dict[str, int] = {}
    for a, b in zip(words, words[1:]):
        if a not in JD_STOPWORDS and b not in JD_STOPWORDS:
            bg = f"{a} {b}"
            bigrams[bg] = bigrams.get(bg, 0) + 1
    for bg, n in bigrams.items():
        if n >= 2:  # a repeated phrase outranks its component words
            freq[bg] = n * 2
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(t, n) for t, n in ranked if n >= 2][:top_n]


def term_present(term: str, text_lower: str) -> bool:
    pat = r"\b" + r"\s+".join(re.escape(w) for w in term.split()) + r"\b"
    return re.search(pat, text_lower) is not None


def check_links(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Fetch http(s)/www URLs found in the text. Returns (ok/noted, [(url, problem)])."""
    import urllib.error
    import urllib.request
    found = re.findall(r"(?:https?://|www\.)[^\s)\]>\"',;]+", text)
    urls = sorted({("https://" + u if u.startswith("www.") else u).rstrip(".") for u in found})[:10]
    ok, bad = [], []
    for u in urls:
        host = re.sub(r"^https?://(?:www\.)?", "", u).split("/")[0]
        if "linkedin.com" in host:
            ok.append(u + " (linkedin blocks bots - verify by eye)")
            continue
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=6) as r:
                (ok if r.status < 400 else bad).append(
                    u if r.status < 400 else (u, f"HTTP {r.status}"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 999):  # bot-blocked or HEAD refused, not necessarily dead
                ok.append(u + f" (HTTP {e.code} to bots - verify by eye)")
            else:
                bad.append((u, f"HTTP {e.code}"))
        except Exception as e:  # noqa: BLE001 - DNS failure, timeout, TLS...
            bad.append((u, type(e).__name__))
    return ok, bad


# --------------------------------------------------------------------------- #
# Listing fitness: trust/quality signals in the job posting itself
# --------------------------------------------------------------------------- #
# (points, label, pattern) - matched against the lowercased posting text.
LISTING_RED_FLAGS = [
    (35, "payment request",
     r"(?:training|registration|application|starter|onboarding)\s+fee"
     r"|pay\s+for\s+your\s+(?:own\s+)?(?:equipment|training|background\s+check)"
     r"|(?:send|transfer)\s+(?:us\s+)?money|western\s+union|moneygram"
     r"|wire\s+transfer|cash\s?app|deposit\s+(?:a|the|our)\s+check"),
    (35, "sensitive data requested up front",
     r"\b(?:ssn|social\s+security\s+number|bank\s+account|routing\s+number"
     r"|passport\s+number|national\s+id)\b"),
    (20, "off-platform contact",
     r"\bwhat'?s\s*app\b|\btelegram\b|text\s+(?:me|us)\s+at"),
    (15, "free-mail contact address",
     r"[a-z0-9._%+-]+@(?:gmail|yahoo|hotmail|outlook|aol|proton(?:mail)?)\."),
    (15, "crypto payment",
     r"paid?\s+in\s+(?:crypto(?:currency)?|bitcoin|usdt|eth)\b"),
    (15, "too good to be true",
     r"no\s+experience\s+(?:necessary|needed|required)|earn\s+up\s+to\s+[$€£]"
     r"|[$€£]\s?\d[\d,.]*\s*(?:per|/|a)\s*(?:day|week)\b|guaranteed\s+income"),
    (12, "MLM / commission-only wording",
     r"unlimited\s+(?:earnings?|income|potential)|be\s+your\s+own\s+boss"
     r"|commission[-\s]only|recruit(?:ing)?\s+(?:new\s+)?(?:members|friends|people)"),
    (10, "urgency pressure",
     r"urgent(?:ly)?\s+hiring|immediate\s+start|start\s+(?:today|immediately)"
     r"|limited\s+(?:slots|spots|positions)|hiring\s+now!"),
    (6, "evergreen / ghost-job wording",
     r"always\s+(?:hiring|accepting)|talent\s+(?:pool|pipeline|community)"
     r"|(?:future|upcoming)\s+opportunit"),
]
LISTING_GREEN_FLAGS = [
    (6, "compensation stated",
     r"[$€£]\s?\d[\d,.]*(?:\s*[-–]\s*[$€£]?\s?\d[\d,.]*)?"
     r"\s*(?:per\s+year|/\s*year|annual|gross|net|k\b)|salary\s+(?:range|band)"),
    (5, "interview process described",
     r"interview\s+process|\b\d\s+(?:stage|round)s?\b|technical\s+interview"),
    (4, "concrete benefits",
     r"health\s+insurance|dental|pension|401\s?k|paid\s+(?:leave|vacation|time\s+off)"
     r"|annual\s+leave|training\s+budget"),
    (3, "reporting line named", r"report(?:s|ing)?\s+to\s+(?:the\s+)?[a-z]"),
]


def vet_listing(jd_text: str) -> tuple[int, list[tuple[int, str, str]]]:
    """Score a job posting's trust/quality signals (0-100, baseline 75).

    Heuristic and TEXT-ONLY: it reads the posting, not the company. Treat it as a
    tripwire for scam and ghost-job patterns, not as a background check.
    """
    low = jd_text.lower()
    findings: list[tuple[int, str, str]] = []

    for pts, label, pat in LISTING_RED_FLAGS:
        m = re.search(pat, low)
        if m:
            findings.append((-pts, label, m.group(0)[:60].strip()))
    for pts, label, pat in LISTING_GREEN_FLAGS:
        m = re.search(pat, low)
        if m:
            findings.append((pts, label, m.group(0)[:60].strip()))

    words = re.findall(r"\S+", jd_text)
    if len(words) < 80:
        findings.append((-12, "thin listing", f"only {len(words)} words"))
    bare = [w.strip("!?.,:;*()-") for w in words]
    caps = [w for w in bare if len(w) >= 4 and w.isalpha() and w.isupper()]
    if jd_text.count("!") >= 4 or (words and len(caps) / len(words) > 0.08):
        findings.append((-8, "shouting (caps/exclamations)",
                         f"{jd_text.count('!')} '!', {len(caps)} ALL-CAPS words"))
    amounts = [float(a.replace(",", "")) * (1000 if k else 1)
               for a, k in re.findall(r"[$€£]\s?(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", low)]
    amounts = [a for a in amounts if a >= 100]
    if amounts and max(amounts) / min(amounts) >= 4:
        findings.append((-8, "implausibly wide pay range",
                         f"{min(amounts):,.0f} .. {max(amounts):,.0f}"))
    if amounts:  # informational (0 points): eyeball these against your salary floor
        shown = re.findall(r"[$€£]\s?\d[\d,.]*\s*k?\b", jd_text, re.IGNORECASE)
        findings.append((0, "amounts mentioned (compare with your floor)",
                         ", ".join(s.strip() for s in shown[:5])))
    sections = len(re.findall(
        r"responsibilit|requirements?|qualifications?|what\s+you.?ll\s+do"
        r"|about\s+(?:the\s+)?role|benefits|we\s+offer", low))
    if sections >= 2:
        findings.append((6, "structured sections", f"{sections} section markers"))

    score = 75 + sum(d for d, _, _ in findings)
    return max(0, min(100, score)), findings


@dataclass
class Check:
    name: str
    status: str  # PASS | WARN | FAIL | INFO
    detail: str = ""


@dataclass
class FileResult:
    path: Path
    fmt: str
    intended: str
    size_kb: float = 0.0
    pages: int | None = None
    text: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    name: str | None = None
    roles: list[dict] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    jd_ratio: float | None = None
    error: str | None = None

    def add(self, name, status, detail=""):
        self.checks.append(Check(name, status, detail))

    @property
    def score(self) -> int:
        s = 100
        for c in self.checks:
            if c.status == "FAIL":
                s -= 15
            elif c.status == "WARN":
                s -= 5
        return max(0, s)


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def run_pdftotext(path: Path, *flags: str) -> str:
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError("pdftotext not found on PATH")
    cmd = [exe, "-enc", "UTF-8", *flags, str(path), "-"]
    out = subprocess.run(cmd, capture_output=True, timeout=60)
    return out.stdout.decode("utf-8", errors="replace")


def pdf_info(path: Path) -> dict[str, str]:
    """Best-effort read of the PDF Info dictionary (Author/Title/Creator/Producer)."""
    data = path.read_bytes()[:400_000]
    props: dict[str, str] = {}
    for key in (b"Author", b"Title", b"Creator", b"Producer"):
        m = re.search(rb"/" + key + rb"\s*\(([^)]{1,150})\)", data)
        if not m:
            continue
        raw = m.group(1)
        if raw.startswith(b"\xfe\xff"):
            val = raw[2:].decode("utf-16-be", "replace")
        else:
            val = raw.decode("latin-1", "replace")
        val = val.replace("\\(", "(").replace("\\)", ")").strip()
        if val:
            props[key.decode()] = val
    return props


def extract_pdf(path: Path) -> dict:
    reading = run_pdftotext(path)          # reading-order (what a good ATS approximates)
    layout = run_pdftotext(path, "-layout")  # preserves columns -> reveals multi-column
    raw = run_pdftotext(path, "-raw")       # content-stream order (naive ATS) -> reveals jumble
    pages = reading.count("\f") + 1 if reading else 0
    return {"reading": reading, "layout": layout, "raw": raw, "pages": pages,
            "info": pdf_info(path)}


def _xml_text(xml: str) -> str:
    """Extract visible text from a WordprocessingML part, preserving paragraph/cell breaks.

    Converts structural tags to whitespace, then strips remaining tags while keeping the
    text nodes AND the inserted whitespace (so paragraphs don't collapse into one blob).
    """
    xml = re.sub(r"<w:instrText\b[^>]*>.*?</w:instrText>", "", xml, flags=re.DOTALL)
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"</w:tc>", "\t", xml)
    xml = re.sub(r"<w:tab\b[^>]*/?>", "\t", xml)
    xml = re.sub(r"<w:br\b[^>]*/?>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", xml)  # keeps text nodes + the whitespace inserted above
    return html.unescape(text.replace("\r", ""))


def _core_prop(xml: str, tag: str) -> str:
    m = re.search(rf"<(?:dc|cp):{tag}[^>]*>(.*?)</(?:dc|cp):{tag}>", xml, re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else ""


def extract_docx(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        doc = z.read("word/document.xml").decode("utf-8", errors="replace")
        body = _xml_text(doc)
        hdr_ft = ""
        for n in names:
            if re.search(r"word/(header|footer)\d*\.xml$", n):
                hdr_ft += _xml_text(z.read(n).decode("utf-8", errors="replace")) + "\n"
        media = [n for n in names if n.startswith("word/media/")]
        n_tables = doc.count("<w:tbl>")
        has_textbox = bool(re.search(r"txbxContent|<w:drawing|<wps:txbx", doc))
        core = ""
        if "docProps/core.xml" in names:
            core = z.read("docProps/core.xml").decode("utf-8", errors="replace")
        meta = {k: _core_prop(core, k) for k in ("title", "creator", "lastModifiedBy")}
        has_comments = any(n.endswith("word/comments.xml") for n in names)
        has_tracked = bool(re.search(r"<w:(?:ins|del)\b", doc))
    return {
        "text": body,
        "header_footer": hdr_ft,
        "n_tables": n_tables,
        "has_textbox": has_textbox,
        "n_images": len(media),
        "meta": meta,
        "has_comments": has_comments,
        "has_tracked": has_tracked,
    }


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def norm_month(mon: str, year: str) -> tuple[int, int]:
    return int(year), MONTHS[mon.lower().rstrip(".")]


def parse_end(tok: str) -> tuple[int, int]:
    if re.match(r"present|current", tok, re.IGNORECASE):
        return TODAY
    m = re.match(rf"({MONTH_RE})\.?\s+(\d{{4}})", tok, re.IGNORECASE)
    return norm_month(m.group(1), m.group(2))


ROLE_WORDS = {
    "operations", "delivery", "engineer", "manager", "senior", "lead", "leader",
    "specialist", "analyst", "itsm", "security", "identity", "endpoint", "service",
    "integration", "support", "administrator", "technician", "consultant", "director",
}


def guess_name(lines: list[str]) -> str | None:
    """First top-of-document line that looks like a person name (not a role/eyebrow label)."""
    for ln in lines[:12]:
        s = ln.strip()
        words = s.split()
        if not (2 <= len(words) <= 4):
            continue
        if not all(re.fullmatch(r"[A-Za-z.\-]+", w) for w in words):
            continue
        if any(w.lower() in ROLE_WORDS for w in words):
            continue
        if s.isupper() or all(w[0].isupper() for w in words):
            if len(s) >= 6:
                return s
    return None


def canon_company(company: str) -> str:
    """Normalize an employer name so the same company matches across files.

    Drops parentheticals ("(now X)", "(AC)"), punctuation, legal suffixes and
    stray single letters, so "Acme Group (now Zenith)" == "Acme Group Inc.".
    """
    c = re.sub(r"\([^)]*\)", "", company)
    c = re.sub(r"[.,]", " ", c)
    c = re.sub(r"\b(?:inc|ltd|llc|gmbh|srl|sa|plc|corp|co|group)\b", "", c,
               flags=re.IGNORECASE)
    c = re.sub(r"\b[A-Za-z]\b", "", c)
    c = re.sub(r"\s+", " ", c).strip()
    return (c or company.strip()).title()


def parse_roles(text: str) -> list[dict]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    roles: list[dict] = []
    for i, ln in enumerate(lines):
        m = DATE_RANGE_RE.search(ln)
        if not m:
            continue
        start = norm_month(m.group(1), m.group(2))
        end = parse_end(m.group(3))
        label = ln[:m.start()].strip(" \t,-|·")
        # date sat on its own line, or under an italic "Official title:" note -> look back
        if len(label) < 3 or label.lower().startswith("official title"):
            for j in range(i - 1, max(-1, i - 5), -1):
                cand = lines[j].strip()
                if not cand or cand.lower().startswith("official title"):
                    continue
                label = cand
                if "," in cand:  # prefer a real "Title, Company" header
                    break
        title, company = label, ""
        if "," in label:
            title, company = label.rsplit(",", 1)
        role = {
            "title": title.strip(), "company": company.strip(),
            "canon": canon_company(company or title),
            "start": start, "end": end,
        }
        # de-dupe (same date range can appear on continuation pages)
        if not any(r["start"] == start and r["end"] == end and r["canon"] == role["canon"]
                   for r in roles):
            roles.append(role)
    return roles


def fmt_ym(ym: tuple[int, int]) -> str:
    return f"{ym[0]:04d}-{ym[1]:02d}"


def months_between(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (b[0] - a[0]) * 12 + (b[1] - a[1])


# --------------------------------------------------------------------------- #
# Per-file evaluation
# --------------------------------------------------------------------------- #
def infer_intended(name: str) -> str:
    n = name.lower()
    if "ats" in n:
        return "ATS-critical"
    if "technical" in n:
        return "ATS-critical"
    if "leadership" in n or "designed" in n or "human" in n:
        return "Human-facing (designed)"
    return "General"


def evaluate(path: Path, keywords: list[str] | None = None,
             jd: list[tuple[str, int]] | None = None,
             links: bool = False) -> FileResult:
    fmt = path.suffix.lower().lstrip(".")
    res = FileResult(path=path, fmt=fmt, intended=infer_intended(path.name),
                     size_kb=round(path.stat().st_size / 1024, 1))
    try:
        if fmt == "pdf":
            pdf = extract_pdf(path)
            res.text = pdf["reading"]
            res.pages = pdf["pages"]
            _pdf_checks(res, pdf)
        elif fmt == "docx":
            dx = extract_docx(path)
            res.text = dx["text"]
            _docx_checks(res, dx)
        else:
            res.error = f"unsupported format: {fmt}"
            return res
    except Exception as e:  # noqa: BLE001 - one bad file must not abort the run
        res.error = f"{type(e).__name__}: {e}"
        return res

    _common_checks(res, keywords or KEYWORDS, jd, links)
    return res


def _pdf_checks(res: FileResult, pdf: dict):
    reading, layout, raw = pdf["reading"], pdf["layout"], pdf["raw"]
    n_chars = len(reading.strip())
    if n_chars < 200:
        res.add("Text layer", "FAIL",
                f"only {n_chars} chars extracted - likely scanned/flattened image; ATS reads nothing")
    else:
        res.add("Text layer", "PASS", f"{n_chars:,} chars extractable ({pdf['pages']} page(s))")

    # Multi-column / tile detection: compare reading order vs layout columns.
    col_lines = [ln for ln in layout.splitlines() if re.search(r"\S {3,}\S", ln)]
    ratio = len(col_lines) / max(1, len([l for l in layout.splitlines() if l.strip()]))
    # Isolated metric tokens (e.g. "~500", "40+") that parse without their labels adjacent.
    tile_tokens = re.findall(r"(?m)^\s*(~?\d{2,4}\+?)\s*$", reading)
    if ratio > 0.35 or len(tile_tokens) >= 3:
        res.add("Column/tile layout", "WARN",
                f"multi-column or metric-tile layout detected (dense-column lines={ratio:.0%}, "
                f"isolated numeric tokens={len(tile_tokens)}); order may scramble in strict ATS")
    else:
        res.add("Column/tile layout", "PASS", "single-column reading order looks linear")

    info = pdf.get("info", {})
    title = info.get("Title", "")
    if title and JUNK_TITLE.search(title):
        res.add("Document metadata", "WARN",
                f'stale/recycled title shown to whoever opens it: "{title[:60]}"')
    elif info:
        res.add("Document metadata", "INFO",
                "; ".join(f"{k}={v[:30]}" for k, v in info.items())[:110])


def _docx_checks(res: FileResult, dx: dict):
    n_chars = len(dx["text"].strip())
    if n_chars < 200:
        res.add("Text layer", "FAIL", f"only {n_chars} chars in document.xml")
    else:
        res.add("Text layer", "PASS", f"{n_chars:,} chars in word/document.xml (native ATS read)")

    if dx["has_textbox"]:
        res.add("Text boxes/shapes", "FAIL",
                "content in text boxes or drawing shapes - many ATS DROP this text entirely")
    else:
        res.add("Text boxes/shapes", "PASS", "no text boxes/shapes")

    if dx["n_tables"]:
        res.add("Tables", "WARN",
                f"{dx['n_tables']} table(s) - cell content can be read row-wise/out of order by some ATS")
    else:
        res.add("Tables", "PASS", "no tables (linear paragraphs)")

    # contact info hidden in header/footer is frequently ignored by ATS
    hf = dx["header_footer"]
    if EMAIL_RE.search(hf) or PHONE_RE.search(hf):
        res.add("Contact in header/footer", "FAIL",
                "email/phone sit in header/footer - commonly ignored by ATS; move into body")
    else:
        res.add("Contact placement", "PASS", "contact info in document body, not header/footer")

    if dx["n_images"]:
        res.add("Images", "INFO", f"{dx['n_images']} embedded image(s) (ignored by ATS text parse)")

    if dx["has_comments"] or dx["has_tracked"]:
        res.add("Comments/tracked changes", "WARN",
                "leftover comments or tracked changes - visible to anyone who opens the file")
    meta = {k: v for k, v in dx["meta"].items() if v}
    if meta.get("title") and JUNK_TITLE.search(meta["title"]):
        res.add("Document metadata", "WARN",
                f'stale/recycled title: "{meta["title"][:60]}"')
    elif meta:
        res.add("Document metadata", "INFO",
                "; ".join(f"{k}={v[:30]}" for k, v in meta.items())[:110])


def _common_checks(res: FileResult, keywords: list[str],
                   jd: list[tuple[str, int]] | None, links: bool = False):
    text = res.text
    lines = [l for l in text.splitlines() if l.strip()]

    # ---- contact block ----
    res.emails = sorted(set(EMAIL_RE.findall(text)))
    res.phones = sorted({re.sub(r"[^\d+]", "", p) for p in PHONE_RE.findall(text)
                         if len(re.sub(r"\D", "", p)) >= 9})
    res.name = guess_name(lines)
    if len(res.emails) == 1:
        res.add("Email", "PASS", res.emails[0])
    elif not res.emails:
        res.add("Email", "FAIL", "no email found")
    else:
        res.add("Email", "WARN", f"multiple emails: {', '.join(res.emails)}")
    res.add("Phone", "PASS" if res.phones else "WARN",
            res.phones[0] if res.phones else "no phone parsed")
    res.add("LinkedIn", "PASS" if LINKEDIN_RE.search(text) else "WARN",
            (LINKEDIN_RE.search(text).group(0) if LINKEDIN_RE.search(text) else "none"))
    res.add("Name detection", "PASS" if res.name else "WARN", res.name or "name not clearly at top")

    # ---- sections ----
    low = text.lower()
    found, nonstd = [], []
    heading_lines = [l.strip() for l in lines if len(l.strip()) <= 48
                     and (l.strip().isupper() or l.strip().istitle())]
    for key, syns in STANDARD_SECTIONS.items():
        if any(s in low for s in syns):
            found.append(key)
    for missing in ("experience", "education", "skills"):
        if missing not in found:
            res.add(f"Section: {missing}", "WARN", "standard heading not detected")
    # flag headings ATS won't map to a known field
    known_flat = {s for syns in STANDARD_SECTIONS.values() for s in syns}
    for h in heading_lines:
        hl = h.lower()
        if hl in known_flat or any(hl == s for s in known_flat):
            continue
        if re.search(r"delivery impact|leadership approach|selected|highlights|projects", hl):
            nonstd.append(h)
    res.add("Sections", "PASS", "found: " + ", ".join(found))
    if nonstd:
        res.add("Non-standard headings", "WARN",
                f"{', '.join(sorted(set(nonstd)))} - content still indexed but not field-mapped")

    # ---- work history reconstruction ----
    res.roles = parse_roles(text)
    if len(res.roles) < 2:
        res.add("Work history", "WARN", f"only {len(res.roles)} dated role(s) parsed")
    else:
        ordered = sorted(res.roles, key=lambda r: r["start"])
        problems = []
        for a, b in zip(ordered, ordered[1:]):
            gap = months_between(a["end"], b["start"])
            if gap < -1:
                problems.append(f"overlap {abs(gap)}mo ({a['canon']}/{b['canon']})")
            elif gap > 1:
                problems.append(f"gap {gap}mo ({a['canon']}->{b['canon']})")
        current = [r for r in res.roles if r["end"] == TODAY]
        res.add("Work history", "PASS",
                f"{len(res.roles)} roles parsed with clean date ranges")
        res.add("Timeline continuity",
                "PASS" if not problems else "WARN",
                "chronological, no overlaps/gaps" if not problems else "; ".join(problems))
        res.add("Current role", "PASS" if len(current) == 1 else "WARN",
                f"{len(current)} open-ended role(s)")

    # ---- keyword coverage (generic role profile) ----
    present = [k for k in keywords if k.lower() in low]
    missing = [k for k in keywords if k.lower() not in low]
    pct = len(present) / max(1, len(keywords))
    res.add("Keyword coverage",
            "PASS" if pct >= 0.6 else "WARN",
            f"{len(present)}/{len(keywords)} ({pct:.0%}) present"
            + (f"; notable gaps: {', '.join(missing[:6])}" if missing else ""))

    # ---- job-description match (only with --jd) ----
    if jd:
        hits = [t for t, _ in jd if term_present(t, low)]
        miss = [t for t, _ in jd if not term_present(t, low)]
        res.jd_ratio = len(hits) / max(1, len(jd))
        res.add("JD match", "PASS" if res.jd_ratio >= 0.5 else "WARN",
                f"{len(hits)}/{len(jd)} posting terms ({res.jd_ratio:.0%})"
                + (f"; top missing: {', '.join(miss[:8])}" if miss else ""))

    # ---- formatting hygiene ----
    hostile = {c: d for c, d in HOSTILE_CHARS.items() if c in text}
    if hostile:
        res.add("Character hygiene", "WARN",
                "; ".join(sorted(hostile.values())))
    else:
        res.add("Character hygiene", "PASS", "no soft-hyphens, ligatures or zero-width chars")
    # exotic bullets beyond the safe set
    bullets = set(re.findall(r"(?m)^\s*([^\w\s])\s+\S", text))
    exotic = {b for b in bullets if b not in BULLET_CHARS}
    if exotic:
        res.add("Bullet characters", "WARN", f"non-standard bullet glyphs: {' '.join(exotic)}")

    # ---- live URL check (only with --check-links) ----
    if links:
        ok, bad = check_links(text)
        if bad:
            res.add("Link check", "WARN",
                    "; ".join(f"{u} -> {p}" for u, p in bad[:4]))
        elif ok:
            res.add("Link check", "PASS", f"{len(ok)} URL(s) reachable or noted")
        else:
            res.add("Link check", "INFO", "no URLs found in text")


# --------------------------------------------------------------------------- #
# Cross-file consistency
# --------------------------------------------------------------------------- #
def cross_file(results: list[FileResult]) -> list[str]:
    notes = []
    ok = [r for r in results if not r.error and r.text]

    emails = {r.emails[0] for r in ok if len(r.emails) == 1}
    if len(emails) > 1:
        notes.append(f"FAIL  Email differs across files: {sorted(emails)}")
        for r in ok:
            if r.emails:
                notes.append(f"        - {r.path.name}: {r.emails[0]}")
    elif emails:
        notes.append(f"PASS  Single consistent email across all files: {next(iter(emails))}")

    phones = {r.phones[0] for r in ok if r.phones}
    notes.append((f"PASS  Consistent phone: {next(iter(phones))}" if len(phones) == 1
                  else f"WARN  Phone differs: {sorted(phones)}"))

    names = {r.name for r in ok if r.name}
    if len(names) > 1:
        notes.append(f"INFO  Name rendered differently: {sorted(names)}")

    # employment dates per company across files
    by_company: dict[str, set] = {}
    for r in ok:
        for role in r.roles:
            by_company.setdefault(role["canon"], set()).add(
                (fmt_ym(role["start"]), fmt_ym(role["end"])))
    for comp, ranges in sorted(by_company.items()):
        if len(ranges) > 1:
            notes.append(f"WARN  {comp} dates differ across files: {sorted(ranges)}")
    if all(len(v) == 1 for v in by_company.values()) and by_company:
        notes.append("PASS  Employment dates identical across all files")

    return notes


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
STATUS_TAG = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "INFO": "[INFO]"}


def verdict(res: FileResult) -> str:
    fails = sum(c.status == "FAIL" for c in res.checks)
    warns = sum(c.status == "WARN" for c in res.checks)
    if res.error:
        return "ERROR - could not parse"
    if fails:
        base = "WILL LIKELY MIS-PARSE in strict ATS"
    elif warns:
        base = "PARSES WITH CAVEATS"
    else:
        base = "ATS-READY"
    if res.intended == "Human-facing (designed)" and (fails or warns):
        base += "  (acceptable for a human-facing copy if an ATS twin exists)"
    return base


def print_report(results: list[FileResult]):
    print("=" * 78)
    print("ATS SIMULATION REPORT".center(78))
    print("=" * 78)
    for r in results:
        print(f"\n### {r.path.name}")
        print(f"    format={r.fmt}  size={r.size_kb}KB"
              + (f"  pages={r.pages}" if r.pages else "")
              + f"  intended={r.intended}")
        if r.error:
            print(f"    [FAIL] {r.error}")
            continue
        for c in r.checks:
            line = f"    {STATUS_TAG[c.status]} {c.name}"
            if c.detail:
                line += f": {c.detail}"
            print(line)
        if r.roles:
            print("    -- work history as an ATS would reconstruct it --")
            for role in sorted(r.roles, key=lambda x: x["start"], reverse=True):
                comp = role["company"] or role["canon"]
                print(f"       {fmt_ym(role['start'])} .. {fmt_ym(role['end'])}  "
                      f"{role['title']} @ {comp}")
        print(f"    >> SCORE {r.score}/100 - {verdict(r)}")

    print("\n" + "=" * 78)
    print("CROSS-FILE CONSISTENCY".center(78))
    print("=" * 78)
    for n in cross_file(results):
        print("  " + n)

    print("\n" + "-" * 78)
    print("SUMMARY".center(78))
    print("-" * 78)
    for r in results:
        tag = "ERROR" if r.error else f"{r.score:3d}/100"
        print(f"  {tag}  {r.path.name}")


def gap_analysis(gap_dir: Path, results: list[FileResult]) -> None:
    """Aggregate demand for terms across many saved postings; flag uncovered ones."""
    postings = sorted(list(gap_dir.glob("*.txt")) + list(gap_dir.glob("*.md")))
    if not postings:
        print(f"\nNo .txt/.md postings found in {gap_dir}", file=sys.stderr)
        return
    demand: dict[str, int] = {}
    for p in postings:
        for t, _ in extract_jd_terms(p.read_text(encoding="utf-8", errors="replace")):
            demand[t] = demand.get(t, 0) + 1
    texts = [r.text.lower() for r in results if r.text]
    print("\n" + "-" * 78)
    print(f"MARKET GAP ANALYSIS ({len(postings)} postings)".center(78))
    print("-" * 78)
    ranked = sorted(demand.items(), key=lambda kv: (-kv[1], kv[0]))
    shown = 0
    for term, n in ranked:
        if n < 2 and len(postings) > 2:
            continue  # ignore terms only one posting cares about
        covered = any(term_present(term, t) for t in texts) if texts else None
        mark = ("" if covered is None else
                "covered" if covered else ">> MISSING from every resume")
        print(f"  {n:2d}/{len(postings)}  {term:<32} {mark}")
        shown += 1
        if shown >= 25:
            break
    if texts:
        missing = [t for t, n in ranked if n >= 2
                   and not any(term_present(t, x) for x in texts)]
        if missing:
            print("  Highest-value additions (learn, certify, or say it explicitly): "
                  + ", ".join(missing[:8]))


def tracker_report(path: Path) -> None:
    """Status breakdown, response rate per variant, and follow-up dues from tracker.csv."""
    import csv
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        print(f"\nTracker {path} has no rows.", file=sys.stderr)
        return
    today = datetime.date.today()
    print("\n" + "-" * 78)
    print(f"TRACKER ({len(rows)} rows)".center(78))
    print("-" * 78)
    by_status: dict[str, int] = {}
    for r in rows:
        s = (r.get("status") or "?").strip().lower() or "?"
        by_status[s] = by_status.get(s, 0) + 1
    print("  Status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))

    responded = {"interview", "offer", "rejected"}  # employer reacted at all
    per_variant: dict[str, list[int]] = {}
    for r in rows:
        s = (r.get("status") or "").strip().lower()
        if s in responded or s == "applied":
            v = (r.get("variant_sent") or "?").strip() or "?"
            per_variant.setdefault(v, []).append(1 if s in responded else 0)
    for v, xs in sorted(per_variant.items()):
        print(f"  {v}: {sum(xs)}/{len(xs)} responses ({sum(xs) / len(xs):.0%})")

    due, stale = [], []
    for r in rows:
        s = (r.get("status") or "").strip().lower()
        try:
            d = datetime.date.fromisoformat((r.get("date") or "").strip())
        except ValueError:
            continue
        age = (today - d).days
        label = f"{r.get('company', '?')} / {r.get('role', '?')} ({age}d)"
        if s == "applied" and age >= 8:
            due.append(label)
        elif s.startswith("parked") and age >= 3:
            stale.append(label)
    if due:
        print("  FOLLOW UP (applied 8+ days ago, no response): " + "; ".join(due[:8]))
    if stale:
        print("  STALE PARKED (answer the stuck questions, go finish): "
              + "; ".join(stale[:8]))
    if not due and not stale:
        print("  Nothing due - no follow-ups or stale parked rows.")


def gather(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        pth = Path(p)
        if pth.is_dir():
            files += sorted(pth.glob("*.pdf")) + sorted(pth.glob("*.docx"))
        elif pth.is_file():
            files.append(pth)
        else:
            print(f"warning: not found: {p}", file=sys.stderr)
    # de-dupe, keep order
    seen, out = set(), []
    for f in files:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser(description="ATS simulator for resume files")
    ap.add_argument("paths", nargs="*", default=[DEFAULT_DIR],
                    help="resume files and/or directories to scan")
    ap.add_argument("--json", metavar="PATH", help="also write machine-readable results")
    ap.add_argument("--keywords", metavar="FILE",
                    help="text file, one keyword/phrase per line (replaces built-in profile)")
    ap.add_argument("--jd", metavar="FILE",
                    help="job-description text file to score each resume against")
    ap.add_argument("--gap", metavar="DIR",
                    help="folder of saved postings (.txt/.md); ranks most-demanded terms "
                         "across them and flags those missing from every scanned resume")
    ap.add_argument("--tracker", metavar="FILE",
                    help="tracker.csv; prints status breakdown, response rates and dues")
    ap.add_argument("--check-links", action="store_true",
                    help="fetch http(s)/www URLs found in each resume and flag dead ones")
    args = ap.parse_args()

    keywords = None
    if args.keywords:
        keywords = [ln.strip() for ln in
                    Path(args.keywords).read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.strip().startswith("#")]
    jd, listing = None, None
    if args.jd:
        jd_text = Path(args.jd).read_text(encoding="utf-8", errors="replace")
        jd = extract_jd_terms(jd_text)
        listing = vet_listing(jd_text)
        if not jd:
            print("warning: --jd file yielded no scoreable terms (posting too short?)",
                  file=sys.stderr)

    files = gather(args.paths)
    standalone = listing is not None or args.gap or args.tracker
    if not files and not standalone:
        print("No .pdf/.docx files found.", file=sys.stderr)
        sys.exit(2)

    results = [evaluate(f, keywords, jd, args.check_links) for f in files]
    if results:
        print_report(results)

    if jd and results:
        print("\n" + "-" * 78)
        print("JD MATCH RANKING".center(78))
        print("-" * 78)
        for r in sorted((r for r in results if r.jd_ratio is not None),
                        key=lambda r: -r.jd_ratio):
            print(f"  {r.jd_ratio:4.0%}  {r.path.name}")
        print("  terms scored (freq): " + ", ".join(f"{t}({n})" for t, n in jd[:12]))

    if listing is not None:
        score, findings = listing
        band = ("healthy signals" if score >= 80 else
                "mixed - do the manual company checks" if score >= 55 else
                "HIGH RISK - treat as a suspect posting until verified")
        print("\n" + "-" * 78)
        print("LISTING FITNESS (posting quality / trust signals)".center(78))
        print("-" * 78)
        print(f"  Score: {score}/100 - {band}")
        for delta, label, evidence in findings:
            print(f"  [{delta:+3d}] {label}" + (f': "{evidence}"' if evidence else ""))
        if not findings:
            print("  (no notable signals either way)")
        print("  Note: this scores the posting TEXT only - it is not a company background")
        print("  check. Run the manual verification steps in the playbook before applying.")

    if args.gap:
        gap_analysis(Path(args.gap), results)
    if args.tracker:
        tracker_report(Path(args.tracker))

    if args.json:
        payload = [{
            "file": str(r.path), "format": r.fmt, "intended": r.intended,
            "score": None if r.error else r.score, "error": r.error,
            "jd_ratio": r.jd_ratio,
            "emails": r.emails, "phones": r.phones, "name": r.name,
            "roles": [{**role, "start": fmt_ym(role["start"]), "end": fmt_ym(role["end"])}
                      for role in r.roles],
            "checks": [vars(c) for c in r.checks],
        } for r in results]
        out: dict = {"files": payload}
        if listing is not None:
            score, findings = listing
            out["listing"] = {"score": score, "findings": [
                {"points": d, "label": l, "evidence": e} for d, l, e in findings]}
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nJSON written to {args.json}")


if __name__ == "__main__":
    main()
