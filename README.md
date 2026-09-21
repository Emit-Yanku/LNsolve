# The Job-Application Kit

A repeatable, verifiable system for building CVs that survive both **robots** (ATS —
applicant tracking systems) and **humans** (hiring managers), keeping every document
consistent with your LinkedIn, vetting and pricing every job listing, tailoring each
application to its posting — and carrying you from there through interview prep to
the offer, all from one facts file.

This playbook was distilled from a real job search. Every rule in it exists because
skipping it caused a concrete, observed problem. Copy this folder, follow the phases in
order, and you can reproduce the whole system for yourself or someone else.

**The kit is three files:**

| File | What it is |
|---|---|
| `README.md` | This playbook — process, checklists, and copy-paste AI prompts |
| `ats_check.py` | An ATS simulator that parses your CV files the way real ATS do and reports what breaks |
| `tracker.template.csv` | Starter application tracker — copy to `tracker.csv` (gitignored) and fill as you go |

**The ten phases at a glance:**

| # | Phase | Output |
|---|---|---|
| 0 | Gather | one folder of raw material (CV + LinkedIn exports) |
| 1 | Audit | prioritized list of what's broken and inconsistent |
| 2 | Facts interview | `FACTS.md` — single source of truth, incl. salary floors |
| 3 | Generate | three CV variants (HTML-first → PDF/DOCX) |
| 4 | Verify | `ats_check.py` green across every file |
| 5 | Sync LinkedIn | profile agrees with every document |
| 6 | Apply strategically | vetted, priced, tailored applications + tracker |
| 7 | Assisted runs | model fills, human approves every submit |
| 8 | Interview prep | STAR story bank from FACTS.md + archived posting |
| 9 | Offer | package valued against your floors, counter drafted |

---

## The concept in one paragraph

One CV is always a compromise. Instead, maintain a **facts file** (single source of
truth), generate **three CV variants** from it (a technical one-pager, a designed
"leadership" version for humans, and an ATS-safe twin of it for portals), keep all of
them **byte-consistent with each other and with LinkedIn** (same email, phone, titles,
dates), **machine-verify** everything with the simulator before sending anything, and
**tailor keywords per job posting** using the `--jd` matcher. The result: nothing you
submit ever contradicts anything else you've published, and nothing gets silently
mangled by a resume parser. The last mile is an **assisted application run** (Phase
7) — a model drives your browser and fills the forms while you approve every submit —
and the same facts file then preps the interview (Phase 8) and prices the offer
(Phase 9).

```
FACTS.md  ──►  Technical CV (1p, ATS-safe)      ──►  portals, hands-on roles
(source    ──►  Leadership CV (designed, tiles)  ──►  humans: email, DMs, referrals
of truth)  ──►  Leadership ATS CV (linear twin)  ──►  portals, leadership roles
     │
     └────►  LinkedIn profile (must agree with all of the above)

every arrow is verified by:  python ats_check.py <folder> [--jd posting.txt]
```

---

## Requirements

- **Python 3.10+** — the script is standard-library only, no `pip install` needed.
  - Windows: install from python.org, then run via `py ats_check.py` (the `py`
    launcher works even when the bare `python` command is shadowed by the Microsoft
    Store alias stub — a common Windows trap).
- **`pdftotext`** on PATH (only needed for PDF checking; DOCX works without it):
  - Windows: Xpdf command-line tools from xpdfreader.com (unzip, add `bin64` to PATH),
    or `choco install xpdf-utils`
  - macOS: `brew install poppler`
  - Linux: `sudo apt install poppler-utils`
- Optional: a Chromium browser (Chrome or Edge, already on most machines) for the
  Phase 3 HTML → PDF export.
- Optional but strongly recommended: an **AI assistant** that can read PDF/DOCX files.
  The prompts below are written to be pasted into one.

---

## Phase 0 — Gather the raw material

Collect into one folder:

1. Your **current CV** (whatever state it's in).
2. Your **LinkedIn profile as PDF**: profile page → *More* → *Save to PDF*.
3. Your **LinkedIn skills page** saved as HTML or screenshots (the PDF export
   truncates skills).
4. Screenshots of anything else public: recommendations, projects, certifications.

Why LinkedIn too? Because recruiters open your CV and your LinkedIn **side by side**,
and inconsistencies between them (different email, different job title, dates off by a
month) read as carelessness — they damage you more than any weak bullet ever will.

---

## Phase 1 — Audit what you have

Run this checklist against your current CV **and** LinkedIn simultaneously. These are
the failure modes actually found in practice:

- [ ] **One email address everywhere.** Not one provider on the CV and a different,
      older address on LinkedIn. Pick one professional address; change it in every
      file *and* LinkedIn contact info in the same sitting.
- [ ] **Phone in international format** (`+1 …`, `+44 …`, `+81 …`) if you target
      remote or global companies.
- [ ] **Contiguous dates, no accidental overlaps.** A CV saying "Mar 2019" where
      LinkedIn says "Apr 2019" creates a phantom two-job overlap that a sharp
      recruiter (or this kit's script) will flag.
- [ ] **One title per role.** If your official title was awkward, internal-jargon,
      or translated ("Sachbearbeiter Kundenservice II", "Referent Comunicare"),
      pick the clean market-standard version ("Customer Service Representative",
      "Communications Specialist") and use it *everywhere*, with an optional
      one-line "*Official title: …*" note on the CV for honesty.
- [ ] **Numbers for scale.** Budget managed, team size, clients or accounts held,
      revenue influenced, caseload, users supported, units shipped, audience
      reached. Check your own LinkedIn Projects section first — people often
      already wrote the numbers there and forgot to put them in the CV.
- [ ] **Every metric attributed to its context.** "$2M budget" — which year, which
      team, which product line? Numbers from different eras shown side by side must
      be labeled ("2022 portfolio", "at peak season") or an interviewer will catch
      the apparent contradiction.
- [ ] **Certifications vs. coursework separated.** Online courses are not
      certifications. Label the section honestly ("Professional Development") and
      invest in **one real role-based credential** — the one that names your target
      title: ITIL for service management, CPA/ACCA for accounting, PMP for delivery,
      Google Ads for performance marketing, AWS SAA for cloud. One real credential
      outweighs ten course completions.
- [ ] **No skills you can't defend.** A tool you've only done a course on — a
      language, a platform, a statistics package — gets cut or marked
      "(foundational)". Listing it as a skill invites the one interview question
      you can't answer.
- [ ] **Work-mode signals agree.** CV says "(Remote)" while LinkedIn Open-to-Work
      says "On-site · Hybrid" = mixed signal. Align them.
- [ ] **Lead with your differentiator.** The rarest true story you can tell (took a
      product through regulatory approval, opened a new market from zero, turned
      around a failing account, kept operations running through a merger) belongs
      in the headline, not buried in bullet three.
- [ ] **Leadership claims match evidence.** If you want a lead/manager role but have
      no direct reports, say so gracefully — "brings practical project and workstream
      leadership without overstating formal people-management scope" is credible;
      inflated claims are not.

**Copy-paste AI prompt (audit):**

> Here are my CV and my LinkedIn profile export (plus my skills page). Cross-check
> them and report: (1) every factual inconsistency between them — emails, phones,
> job titles, employment dates, certifications, work-mode signals; (2) where I'm
> missing quantification, and which numbers already exist elsewhere in my materials;
> (3) which listed certifications are real credentials vs. course completions;
> (4) any skill I list that my experience can't back up in an interview; (5) my
> strongest differentiator story and whether the documents lead with it. Be specific
> and prioritize by damage.

---

## Phase 2 — Build the source of truth (as an interview, not an extraction)

Create `FACTS.md`. Every document you generate afterwards derives from this file, so a
fact fixed here stays fixed everywhere.

Don't let a model silently extract this from your documents — the documents are the
*problem being fixed*, and silent extraction launders their gaps and vagueness into a
new file. Build it as a **guided Q&A**: the model interviews you topic by topic, digs
for the numbers you forgot you had, challenges each claim the way an interviewer
would, and you confirm every fact before it lands in the file. Template:

```markdown
# FACTS — [Full Name]

## Contact (canonical — used verbatim in every document)
- Name: [Full Name]
- Email: [one.address@example.com]        # the ONE address
- Phone: [+1 555 000 0000]                # international format
- LinkedIn: linkedin.com/in/[handle]
- Location: [City, Country] — [remote / hybrid / on-site preference]

## Positioning
- Target roles: [the 2-3 titles you actually want, e.g. "FP&A Lead", "Finance Manager"]
- Differentiator story: [one sentence — the rare thing that is true about you]
- Honest leadership framing: [e.g., "workstream leadership, no formal reports yet"]

## Role: [Employer] — [Clean Title]
- Official title (if different): [...]
- Dates: [Mon YYYY] – [Mon YYYY | Present]   # must chain cleanly to adjacent roles
- Scope numbers: [budget, team size, clients/accounts, users, volume, audience...]
- Achievements (each with metric + its context/era):
  - [grew retainer accounts from 12 to 31 with zero churn (2023-24 book)]
  - [cut month-end close from 9 days to 4 (FY2024)]

## Certifications (real credentials only)
- [...]
## Professional development (courses)
- [...]
## Education / Languages
- [...]

## Compensation (private — this file is gitignored for a reason)
- Current pay: [gross/month + currency, or n/a]
- FTE floor: [minimum gross/month you would accept as an employee]
- Contractor floor: [minimum monthly invoice or day rate through your own firm]
  # rule of thumb: 1.3-2x the FTE gross — a contractor covers their own taxes,
  # benefits, insurance, equipment, unpaid leave and bench risk
- Dream number: [the offer you would sign without negotiating]
- Non-salary must-haves: [remote %, notice period, training budget, equipment...]
```

**Copy-paste AI prompt (facts interview):**

> Interview me to build my FACTS.md — do not just extract it from my documents.
> Use this template: [paste template]. My CV and LinkedIn export are attached as
> the starting point, not as the truth. Rules:
> (1) one topic at a time, at most three questions per message;
> (2) for every role, probe for what the documents don't say: scope numbers
> (budget, team size, clients, users, volume), before/after outcomes, and which
> year or cohort each number belongs to;
> (3) when I state a claim, ask how I would prove it if an interviewer pushed
> back — if I can't, soften it or drop it;
> (4) chase every vague word ("improved", "helped with", "involved in") until it
> becomes a number or a concrete story;
> (5) ask about each transition between roles, so every date, gap, and overlap
> has an explanation;
> (6) finish with compensation: my current pay, then my minimum monthly floor as
> an employee (FTE) and my minimum as a contractor through my own firm — and hold
> me to the 1.3-2x rule if my contractor floor comes out too close to my FTE
> floor;
> (7) then output the complete FACTS.md and read the ten most load-bearing claims
> back to me for an explicit yes/no on each.

---

## Phase 3 — Generate the three variants

All three come **from FACTS.md only** — never from each other, never from memory.

### Naming convention (the script keys off it)

```
Firstname_Lastname_Technical_CV.pdf / .docx
Firstname_Lastname_Leadership_CV.pdf / .docx        <- the designed, human-facing one
Firstname_Lastname_Leadership_ATS_CV.pdf / .docx    <- its ATS-safe twin
```

Keep your **name in the filename** — some ATS ingest the filename as a field. Files
named `CV_final_v3.pdf` throw that away.

The variant *axis* is yours to rename — "Technical vs Leadership" fits many careers,
but "Clinical vs Administrative", "Creative vs Strategy", or "Engineering vs
Product" work identically. Whatever you call them, keep `ATS` in the ATS twin's
filename (and `Technical` or `ATS` in your strict single-column variant's) — the
checker infers each file's intended standard from its name.

### Rules per variant

**Technical CV** (for hands-on/IC roles, and the safest portal upload):
- One page. Single column. No tables, no text boxes, no images, no columns.
- Standard headings only: *Profile, Core Skills, Professional Experience, Education,
  Languages* — ATS map these words to database fields; creative headings don't map.
- Contact block in the **body**, never in the page header/footer (many ATS ignore
  headers/footers entirely).
- Keywords written into sentences, acronyms spelled out once each:
  "Customer Relationship Management (CRM)", "Accounts Payable (AP)".

**Leadership CV — designed** (for human eyes only):
- Two pages max. A metric-tile band up top is allowed and effective
  (`$3.2M budget · 14 direct reports · 27 markets`), **but**:
  - label every tile with its context/era so numbers from different periods can't be
    misread as one claim;
  - repeat every tile number inside an experience bullet — then even if a parser
    scrambles the tile table, no unique information is lost.
- May include narrative sections (*Leadership Approach*, *Selected Delivery Impact*),
  accepting that ATS index but don't field-map them.
- Never enters an application portal. Email, DMs, referrals only.

**Leadership ATS CV** (same content, ATS-safe container):
- Take the designed version and **re-house, don't rewrite**: fold tile numbers into
  sentences ("owns a $3.2M budget across 27 markets…"), drop the tile table, keep single
  column. In a real measurement, designed vs. ATS twin were **97% word-identical** —
  ATS-readiness is a property of *structure*, not vocabulary.

### Author in HTML, export to PDF and DOCX

Don't have a model wrestle binary formats directly — models are far more reliable
at **HTML + CSS** than at Word layouts, and one HTML template styles a variant
deterministically (print CSS gives exact A4 page control, page breaks, and the
designed version's metric tiles). The flow:

1. Model generates each variant as an `.html` file **from FACTS.md**.
2. **PDF**: print the HTML headlessly — `chrome --headless --print-to-pdf=out.pdf
   cv.html` (Edge works identically on Windows) — this keeps a real text layer.
3. **DOCX**: generate it from the same FACTS content (a docx-capable model/skill,
   or `pandoc cv.html -o cv.docx`). The ATS variants are deliberately plain, so
   nothing meaningful is lost in translation.
4. HTML is a *rendering source*, never a fourth source of truth — regenerate all
   formats together so they can't drift, and **always re-run `ats_check.py` on
   the exports** (an export step is exactly where text layers and metadata go
   quietly wrong).

**Copy-paste AI prompt (generation):**

> Using ONLY the attached FACTS.md, generate three CVs following these rules:
> [paste the three rule blocks above]. Produce each as both .docx and .pdf, named
> `Firstname_Lastname_<Variant>_CV.<ext>`. Do not invent any fact, number, employer,
> or date not present in FACTS.md. Where the designed version uses a metric tile,
> ensure the same number also appears in a bullet.

---

## Phase 4 — Verify with the simulator

```bash
python ats_check.py path/to/cv_folder
```
(`py ats_check.py …` on Windows.)

It parses each file the way real ATS do — `pdftotext` for PDFs, native
`word/document.xml` for DOCX — and reports per file:

| Check | Catches |
|---|---|
| Text layer | Scanned/flattened PDFs an ATS reads as *empty* |
| Column/tile layout (PDF) | Multi-column or tile layouts that scramble reading order |
| Tables / text boxes (DOCX) | Content many ATS reorder (tables) or drop entirely (text boxes) |
| Contact placement | Email/phone hiding in header/footer |
| Email / phone / LinkedIn / name | Contact block parseability |
| Sections | Missing or non-standard headings |
| Work history reconstruction | The exact title @ company + dates timeline an ATS will build |
| Timeline continuity | Overlaps, gaps, more than one "Present" role |
| Keyword coverage | Gaps vs. a role-keyword profile (`--keywords yourlist.txt` to customize) |
| Character hygiene | Soft hyphens, ligatures, zero-width chars that corrupt extraction |
| Metadata & leftovers | Stale titles ("Microsoft Word - old_v2"), author fields, tracked changes and comments still inside a DOCX |

…then a **cross-file consistency pass**: same email, same phone, identical employment
dates across *every* file — the checks that catch "I fixed it in one variant and
forgot the other two."

**Score bands** (heuristic: −15 per FAIL, −5 per WARN):
- **100** — ATS-ready; upload anywhere.
- **90–95** — parses with caveats; fine if the caveats are deliberate (tiles on the
  designed version) or cosmetic (one unmapped heading).
- **FAIL anywhere** — fix before sending; something will be lost or garbled.

**The loop:** generate → run script → fix every FAIL → fix every cross-file
inconsistency → fix WARNs on the ATS-critical files → regenerate → re-run. Done when
Technical and Leadership-ATS score ≥95 with zero FAILs and all cross-file checks PASS.

**Copy-paste AI prompt (fix loop):**

> Here is the ats_check.py report for my CV folder: [paste]. Fix every FAIL, then
> every cross-file consistency issue, then the WARNs on the ATS-critical files, by
> editing the source documents (or FACTS.md if the fact itself is wrong). Do not
> change any fact — only structure, wording, or genuine errors. Then tell me what
> changed so I can re-run the check.

---

## Phase 5 — Sync LinkedIn

Your uploaded CV is what gets **parsed on application**; your profile is what
recruiters **search**. They must tell the same story:

- [ ] Contact email on LinkedIn = the canonical FACTS.md email.
- [ ] Titles and dates match the CVs month-for-month.
- [ ] About section mirrors the CV profile paragraph (and states target roles).
- [ ] Open-to-Work location/mode matches what the CV signals.
- [ ] Skills curated to ~25 strong ones; pin the top 5 that match your target title.
- [ ] Port your quantified achievements into LinkedIn Projects (with the same numbers
      as the CV — no drift).
- [ ] At least two recommendations, ideally one from a direct manager at a recent
      role; request one whenever you leave a job on good terms.

Partial automation, with a caveat: you *can* drop your LinkedIn "Save to PDF"
export into the folder you scan with `ats_check.py`, and the cross-file
consistency pass will catch email/phone/date drift between profile and CVs. But
the export is **lossy** — skills, projects, and recommendations get truncated —
so it supplements the visual side-by-side check; it never replaces it.

---

## Phase 6 — Apply strategically

| Channel | File to use |
|---|---|
| Job portal / company ATS (Workday, Greenhouse…) | Technical or Leadership-**ATS**, DOCX or text-PDF |
| LinkedIn Easy Apply | Same as above (PDF is fine — it's text-based and parses clean) |
| Direct email to a hiring manager, recruiter DM, referral | Leadership **designed** |
| Hands-on / IC posting | Technical variant |
| Lead / manager / service-delivery posting | Leadership variant (ATS twin for portals) |

### First: vet the listing before you invest in it

A perfect application to a scam or a ghost job is wasted effort at best and identity
theft at worst. The same `--jd` run scores the **posting itself** (and works
standalone, with no CV files at all):

```
LISTING FITNESS (posting quality / trust signals)
  Score: 0/100 - HIGH RISK - treat as a suspect posting until verified
  [-35] payment request: "registration fee"
  [-35] sensitive data requested up front: "ssn"
  [-20] off-platform contact: "whatsapp"
  [-15] free-mail contact address: "hiringteam2026@gmail."
```

**Red flags (deduct):** requests for money or fees, ID/bank data requested at
application time, WhatsApp/Telegram-only contact, free-mail contact addresses,
too-good-to-be-true pay ("$X per day", "no experience necessary"), MLM /
commission-only wording, urgency pressure, evergreen "talent pool" language,
shouting, implausibly wide pay ranges, thin listings.
**Green flags (add):** stated compensation, structured sections, a described
interview process, concrete benefits, a named reporting line.
Baseline 75; **≥80** healthy · **55–79** mixed, verify manually · **<55** high risk.

**The score reads the posting text only — it cannot vouch for the company.** Before
any interview, do the checks a text scan can't:

- [ ] Company site on its **own domain**, with this job on its careers page.
- [ ] LinkedIn company page: plausible headcount, real employees with history, and
      the recruiter who contacted you actually works there.
- [ ] Independent reviews (Glassdoor etc.) and a national business-registry lookup.
- [ ] Recruiter's email domain matches the company domain (never free-mail).
- [ ] Interviews on official channels — never chat-app-only, never "hired" with no
      interview.
- [ ] **Never** pay anything, buy equipment, cash checks, or hand over ID/bank data
      before a signed contract — payment details belong in payroll onboarding, after.

**On LinkedIn specifically, the platform hands you free signals — read them:**

- [ ] **Verification shield on the listing** (the ✓ next to the job title): the
      poster or company passed a LinkedIn verification. Its absence isn't damning
      on its own — but it means you do the next check.
- [ ] **"Meet the hiring team" click-through:** is the job poster a named person
      with real history and mutual connections? Open their profile's
      *Verifications* panel — and read **what** it attests and **when**. A
      work-email verification from a *previous employer* proves they're a real
      person, not that they work where the listing claims they do now.
- [ ] **"Confidential" / unnamed company postings:** legitimate confidential
      searches exist, but you can verify nothing — no shield, no company page, no
      reviews. Treat as high caution: share only what you'd give a stranger, and
      expect the company name before any interview.
- [ ] **Posting meta-signals:** age, applicant count, and response insights.
      "Actively reviewing applicants" on a fresh post beats "No response insights
      available yet" on an old one with 100+ applicants — the latter pattern
      smells like a ghost job.

**Then the vibe check:** search `"<company name>" reddit` plus recent news for the
last 6–12 months. You're looking for *patterns* of complaints — unpaid or late
salaries, interview ghosting, bait-and-switch offers, layoff chaos — not one
grumpy post. Employees complain where the company can't moderate.

**Copy-paste AI prompt (company due diligence):**

> Here is a job posting and the company name: [paste]. Research and report:
> (1) does the company's own site list this job; (2) on LinkedIn — does the listing
> carry a verification shield, does the company page have plausible age and
> headcount, and does the "hiring team" poster check out, including whether their
> profile verifications match their *claimed current employer* or are stale from a
> previous one; (3) independent reviews and any scam reports naming the company;
> (4) Reddit and news from the past 6–12 months — any pattern of complaints (pay,
> ghosting, bait-and-switch)?; (5) business-registry presence; (6) does the contact
> email domain match the company domain. End with a verdict — proceed / proceed
> with caution / avoid — with evidence links.

### Price the role against your floor

Applying is effort; know the number before you spend it. If the posting states pay,
the listing-fitness output prints every amount it found — compare those against your
floors directly. Most postings don't state pay, so estimate:

**Copy-paste AI prompt (salary estimate vs. floor):**

> Here is a job posting [paste] and the Compensation section of my FACTS.md
> [paste]. Estimate the realistic gross salary range per month for this role in
> this market, based on the role, seniority, location, remote/on-site mode, and
> company type — and say what you're basing the estimate on. Then give the
> equivalent contractor/B2B monthly rate (1.3-2x FTE gross). Compare both against
> my FTE floor and my contractor floor, and end with exactly one verdict:
> **apply** / **apply, but anchor negotiation at [X]** / **skip — below floor**.

Decision rule: below floor with no negotiation room → skip without guilt; near the
floor → apply and anchor above it; comfortably above → apply. Model estimates are
directional — sanity-check anything borderline against sources that publish real
ranges (Glassdoor, Payscale, levels.fyi, local job boards) before turning it down.

**Optional, but the highest-yield move in the whole phase — warm it up first.**
Cold applications are the worst-converting channel. Before applying cold, spend
two minutes checking for a warm path: a 1st/2nd-degree connection at the company
(ask for a referral — most companies pay referral bonuses, so you're doing them a
favor), or the recruiter/hiring manager directly (connection note, LinkedIn's
~300-char limit: one line of genuine specific interest + one line of fit). If a
cover letter is wanted: ≤150 words, generated from FACTS.md, mirroring the
posting's own vocabulary — never generic praise. Note any referral in the
tracker's notes column. Skip all of this freely when speed matters more; it's
leverage, not homework.

**Per application** — this is where rankings are actually won:

```bash
python ats_check.py cv_folder --jd postings/2026-01-15-acme.txt
```

Save every posting's full text as `postings/YYYY-MM-DD-company.txt` (the folder is
gitignored). This is deliberate, not clerical: postings get taken down — often
*before* your interview — and the archived text is your Phase 8 syllabus and the
`--gap` corpus below. The script extracts the posting's
salient terms (frequency-weighted words and repeated phrases), scores each CV against
them, and lists the **top missing terms**. Patch the genuinely-true ones into the
variant you're submitting — literal strings matter, because ATS rank on near-exact
matches ("SEO" and "search engine optimization" are different tokens to a parser;
include both). Never add a term that isn't true of you; the CV gets you the interview, and the
interview tests the CV.

Track every posting you evaluate — applied or not — in the tracker: copy
`tracker.template.csv` to `tracker.csv` (gitignored, because it fills with personal
data) or import it into Excel/Sheets. One row per posting:

`date · company · role · posting URL · platform (LinkedIn/Greenhouse/Workday/…) ·
account email · password-manager ref · variant sent · JD match % · listing fitness ·
estimated salary/month · floor verdict · status · stuck questions · next action ·
notes`

Patterns in it (which variant converts, which keywords recur, whether below-floor
"maybes" ever become above-floor offers — they rarely do) feed back into FACTS.md.
Don't eyeball the patterns — ask the script:

```bash
python ats_check.py --tracker tracker.csv
```

prints the status breakdown, response rate per variant, rows due a follow-up nudge
(applied 8+ days, still silent), and parked rows going stale.

### Read the market, not just the posting

Once `postings/` holds a handful of JDs, aggregate them:

```bash
python ats_check.py cv_folder --gap postings/
```

This ranks the most-demanded terms **across every posting you've saved** and flags
the ones missing from all your CVs. One posting asking for a certification is
noise; eight postings asking is your answer to "what do I learn or certify next" —
it turns the Phase 1 credential advice from a guess into a measurement.

**Copy-paste AI prompt (tailoring):**

> Here is a job posting and the ats_check.py --jd report for my CV against it:
> [paste both]. For each missing term, tell me whether my FACTS.md supports claiming
> it. Patch the supported ones naturally into the [variant] CV — no keyword stuffing,
> no invented experience — and flag the unsupported ones as interview-prep gaps.

---

## Phase 7 — Assisted application runs (the human stays on the trigger)

The endgame: an AI that drives your **real browser** — reading postings, vetting,
pricing, picking the CV variant, filling the forms — while you approve each
submission. In Claude's ecosystem that's the desktop app driving the *Claude in
Chrome* extension (your own Chrome, your own logged-in LinkedIn), with computer use
for anything outside the browser; other AI stacks have equivalents.

**Full autonomy is the wrong goal, not a missing feature.** Every submission is an
irreversible, outward-facing act in your name: one wrongly-guessed screening answer
misrepresents you, duplicate or sloppy applications burn your reputation with
recruiters who remember names, and job platforms prohibit unattended automation.
Assistants also (correctly) refuse to submit forms, log in, create accounts, or
solve CAPTCHAs on their own. So the design is a **copilot loop** — the model does
the reading and the typing, you do the judgment and the click:

| The model does | You do |
|---|---|
| Opens each shortlisted posting, extracts the text | Stay present for the run |
| Vets it: listing fitness, shield, hiring team, "Confidential" caution | Rule on "mixed" verdicts |
| Prices it against your FACTS.md floors | Confirm borderline calls |
| Runs `ats_check.py --jd`, picks the variant, flags missing-but-true keywords | Approve any CV tweak |
| Fills the form from FACTS.md only, attaches the right CV file, drafts each screening answer | Review every field and answer |
| Stops at the submit button | **Give the explicit yes for every submit** |
| Appends every posting to `tracker.csv` | Handle all logins, account creation, and CAPTCHAs |

**Per-run protocol** (one batch of shortlisted jobs, ~5–15 postings):

1. Shortlist from your saved searches; paste the URLs.
2. Per posting: extract → vet → price → match → fill → **your yes** → submit → log.
3. **Nothing is silently dropped — every posting evaluated gets a tracker row.**
   Three non-apply statuses instead of skipping: `declined` (failed vetting or
   below floor — the reason goes in the row), `parked-stuck` (a screening question
   the model can't truthfully answer from FACTS.md — the *exact question* goes in
   the stuck-questions column), and `parked-account` (the platform demands a fresh
   account — see below).
4. End of run: the model reads back every parked row, asks you the stuck questions
   **in one batch**, folds your answers into FACTS.md — so the same question never
   blocks again — then takes you back to finish each parked application.
5. Review the tracker together and feed the patterns back (Phase 6).

**Accounts and passwords (the tracker's most sensitive columns):** many portals
force a new account per company. The human creates it — assistants don't create
accounts or touch passwords, and shouldn't. Generate each password in your
**password manager**, unique per site (random beats any rule; if you set a policy:
minimum 15 characters with at least one uppercase, one number, one symbol). The
tracker records the **email used** and the **manager entry name**
(`pm:acme-greenhouse`) — **never the password itself**. A spreadsheet of plaintext
passwords is precisely the data-harvest payload Phase 6 teaches you not to hand
out, and one leaked file would open every portal account at once.

**Copy-paste AI prompt (application run):**

> Run an assisted application session with me in my browser. Attached: FACTS.md,
> my CV variants, and this shortlist of posting URLs: [paste]. For each posting:
> extract the text; run the vetting checks (listing fitness, verification shield,
> hiring team, Confidential caution); price it against my floors; score it with
> `ats_check.py --jd` and choose the variant; then fill the application **from
> FACTS.md only** — never invent an answer, and show me every screening answer
> before it goes into the form. Stop and wait for my explicit yes before any
> submit. I handle all logins, account creation, and CAPTCHAs myself. Never
> silently drop a posting — give every one a row in tracker.csv. Mark vetting or
> floor failures as `declined` with the reason; when a screening question can't
> be truthfully answered from FACTS.md, or a platform demands a new account, mark
> the row `parked`, record the exact blocker in the stuck-questions column, and
> move on to the next posting. At the end of the run: give me the summary, ask me
> every parked question in one batch, fold my answers into FACTS.md, then take me
> back to finish each parked application. Record account emails and password-
> manager entry names in the tracker — never passwords.

---

## Phase 8 — Interview prep (the facts file becomes a story bank)

Every claim in FACTS.md already survived the "how would you prove it?" test — so
interview prep is half done before it starts. When an application converts:

1. Pull the archived posting from `postings/` — it's the syllabus: what the JD
   emphasizes is what they'll ask about.
2. Turn FACTS achievements into **STAR stories** (Situation, Task, Action,
   Result — the Result is the number already sitting in the file).
3. Rehearse the probe list: the claims an interviewer is most likely to push on,
   with the defense you gave in the facts interview.
4. Rehearse the money question: your floors are already decided — practice saying
   them out loud without flinching.

**Copy-paste AI prompt (interview prep):**

> Here are my FACTS.md and the archived posting for the interview: [paste].
> Produce: (1) the 15 most likely interview questions, derived from what this
> posting emphasizes; (2) for each, which FACTS.md story answers it, in STAR form
> with the numbers; (3) the five claims on my CV an interviewer is most likely to
> probe, each with its one-line defense; (4) the gaps — questions this posting
> will raise that FACTS.md can't answer — so I can prepare honest answers instead
> of being surprised; (5) a rehearsal of the salary question using my floors: an
> anchor, a fallback, and my walk-away line. Then quiz me one question at a time
> and critique my answers against the FACTS stories.

---

## Phase 9 — Offer evaluation (the floors get their moment)

An offer is a package, not a number. Before reacting:

- [ ] Base pay vs. your **FTE floor** — or invoice vs. **contractor floor**
      (still 1.3-2x; an offer that flips you from employee to contractor at the
      same number is a pay cut wearing a costume).
- [ ] Value the rest as money where possible: bonus (guaranteed vs. "target"),
      benefits, training budget, equipment, remote %, PTO, notice period.
- [ ] Check the **non-salary must-haves** — a great number that violates a
      must-have is not a great offer.
- [ ] Never accept or decline in the call. "I'll review and come back by [date]"
      is always available and never counted against you.

**Copy-paste AI prompt (offer evaluation & counter):**

> Here is my offer [paste the full terms] and the Compensation section of my
> FACTS.md. Value the total package per month, compare it to my floor and my
> dream number, and flag any violated must-haves. Then draft the counter: an
> anchor above their offer backed by the one or two strongest FACTS-based
> justifications, a fallback position, and polite walk-away wording if they
> can't reach my floor. Tone: warm, brief, zero apology.

---

## Principles (each one was learned the hard way)

1. **Consistency beats polish.** A beautiful CV that contradicts your LinkedIn loses
   to a plain one that agrees with it.
2. **ATS-readiness is structure, not words.** The designed and ATS variants measured
   97% word-identical; the entire score difference came from a table and a heading.
   You don't rewrite content for robots — you re-house it.
3. **Never trust your eyes — verify with a parser.** Files regenerate, pipelines
   drift, and a human can't see that a PDF's text layer says something different from
   its pixels. The script exists because that exact thing happened.
4. **Every number needs a home.** A metric without its era/cohort label is a
   contradiction waiting for an interviewer to find.
5. **Duplicate decorative data.** Anything shown in a tile, chart, or table must also
   exist in a plain sentence, so nothing is lost when structure is stripped.
6. **Honesty is a positioning strategy.** "Official title:" footnotes and "without
   overstating formal people-management scope" build more trust than inflation.
7. **One real certification outranks a page of coursework.** Pick the one credential
   that names your target role and earn it.
8. **The filename is data.** Put your name in it.
9. **Vet the employer like they vet you.** A listing that asks for money, requests
   ID or bank data up front, or hides behind a free-mail address is itself evidence —
   score it before spending effort on it, and never let a good JD-match % override a
   bad trust score.
10. **Know your number before they ask.** An FTE floor and a contractor floor
    (1.3-2x higher — you're buying your own taxes, benefits, and bench risk)
    decided calmly in FACTS.md beat any number produced live in a negotiation, and
    they make "skip — below floor" a five-second decision.
11. **The model drafts, the human sends.** Every outward, irreversible act — a
    submission, a screening answer, a message to a recruiter — gets human eyes and
    an explicit yes before it happens. Autonomy belongs in the research and the
    typing; judgment stays at the trigger.
12. **Park, don't drop.** Every posting evaluated gets a tracker row; every blocker
    becomes a recorded question for the human; every answered question flows back
    into FACTS.md so it never blocks again. Secrets never ride in the tracker —
    reference the password manager, don't replace it.

---

## Script reference

```
python ats_check.py [PATHS ...] [--jd FILE] [--gap DIR] [--tracker FILE]
                    [--check-links] [--keywords FILE] [--json FILE]

  PATHS        .pdf/.docx files and/or directories (default: current directory)
  --jd         job-posting text file; adds per-file JD match % + ranking + missing
               terms, plus a 0-100 listing-fitness vetting of the posting itself
               (vetting also works standalone, with no CV paths at all)
  --gap DIR    folder of saved postings (.txt/.md); ranks the most-demanded terms
               across the whole market and flags those missing from every resume
  --tracker F  your tracker.csv; status breakdown, response rate per variant,
               follow-up dues (applied 8+ days) and stale parked rows
  --check-links  fetch http(s)/www URLs found in each resume and flag dead ones
               (linkedin URLs are noted, not fetched — it blocks bots)
  --keywords   your own role-keyword list (one term per line, # comments allowed) —
               replaces the built-in IT-operations example profile
  --json       machine-readable dump of every check (for logging or automation)
```

Example `--keywords` profiles for other fields (one term per line in a text file):

```
# marketing.txt          # accounting.txt        # nursing.txt
SEO                      IFRS                    patient care
Google Analytics         month-end close         triage
content strategy         accounts payable        medication administration
CRM                      variance analysis       care plans
paid social              reconciliation          electronic health records
marketing automation     internal audit          BLS certification
```

Filename → intended-use inference: names containing `ATS` or `Technical` are held to
the strict standard; `Leadership`, `designed`, or `human` files are graded as
human-facing.

**Limitations (honest ones):** it's a simulator — Workday, Greenhouse, Lever, and
Taleo each parse slightly differently; scores are directional, not gospel. Date
parsing expects "Mon YYYY – Mon YYYY/Present" in English. The JD term extractor is
frequency-based, so very short postings yield few scoreable terms. It checks
parseability and matching, not whether your CV is *good* — that's what Phases 1–3 are
for.
