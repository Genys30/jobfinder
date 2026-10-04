# JobFinder · Israeli Jobs

A live index of open roles in Israeli hi-tech, public sector, academia, and healthcare.  
Built by [Jenny Sotnik Talisman](https://www.linkedin.com/in/jennysotnik/).

🔗 **[genys30.github.io/jobfinder](https://genys30.github.io/jobfinder/)**

---

## What this repository is

The site, and the data the site reads. Nothing else.

Collection — ~70 scrapers, the runners, the classification and lifetime analysis —
moved to a private repository on 2026-07-24. This one is written only by that
pipeline's publish job, from a manifest, so what you see here is exactly what the
browser fetches: `index.html`, `js/`, `dashboard.html`, and the data files below.

Everything published here before 2026-07-24 is still in this repository's history.
Removing it from the current tree does not unpublish it, and this README does not
pretend otherwise.

---

## How it works

A nightly pipeline scrapes ~90 sources — ATS boards (Comeet, Greenhouse, Lever,
Ashby, Workable, Breezy), hospitals, universities, banks and insurers, ministries
and municipalities — and writes one CSV per source per day. LinkedIn exports are
added by hand each morning.

The frontend has no backend and no database. It fetches:

| File | What it is |
|---|---|
| `jobs_data.json` | every source's last 7 days, bundled — one request instead of ~500 |
| `history.csv` | daily totals, for the trend charts |
| `direct_jobs.csv` | hand-entered postings |
| `data/avodata_salary.json` | Ministry of Labor / CBS 2023 reference wages by ISCO domain |

The footer carries the bundle's own build date. If it reads `data · <an older date>`
rather than `live`, the pipeline has not published since that date — the page is
showing you what it has, and saying so.

---

## How long postings stay up

`jobs_seen.csv` is an append-only ledger — one row per posting, recording the days **we**
observed it rather than whatever date the source claims. It survives the 7-day CSV pruning,
so a posting's lifetime is measurable: it goes back to 2026-04-19.

`ghost_score.py` reads it and answers one question — *how unusual is it that this posting is
still listed?* — as the share of comparable postings from the same employer (or source) still
listed at the same age, estimated with Kaplan-Meier so that postings still open count too.
Sources whose scrapes cannot observe a lifetime are excluded rather than guessed at.

It does **not** claim a posting is fake. A posting leaves a board when someone takes it down,
which is not the same as it being filled, and nothing here measures anyone's intent.

Both the ledger and the scoring live in the private repository. Neither is published.

---

## Sources

| Category | Sources |
|---|---|
| Tech ATS | LinkedIn, Comeet, Greenhouse, Lever, Ashby, Workable, Breezy |
| Public & Defence | MOD, Mitam, Civil Service, BTL, Tel-Aviv |
| Nonprofits & NGOs | Joint (JDC), Biltiformali, Shatil |
| Academia | Weizmann, Technion, HUJI, TAU, BGU, Haifa, Bar-Ilan + colleges |
| Healthcare | Clalit, Ichilov, Rambam, Hadassah, Soroka + 10 medical centers |
| Finance | banks, insurers, cards and investment houses |
| Advisory | KPMG, PwC, BDO, Deloitte, EY |

The full, current list is in the About tab on the site.

---

## License

See [LICENSE](LICENSE) — the code and the data are under different terms.

Code: MIT — take it, run it against the original sources, build your own dataset.  
Data: all rights reserved. Personal use and attributed quoting are fine; bulk
extraction, redistribution and derived datasets are not.

The data was previously offered under ODbL v1.0. That offer was withdrawn on
2026-07-24 and does not apply to anything published on or after that date;
copies taken earlier keep the ODbL terms they were received under.

The ODbL credit in the site footer refers to [techmap](https://github.com/mluggy/techmap),
an upstream source this project reads — not to this project's own data.
