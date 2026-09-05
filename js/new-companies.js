/* JobFinder "New companies" tab — owner-only, embedded (no separate URL).
 *
 * A private mirror + editor for the Case-C watchlist from the separate
 * "new companies discovery" app. That data is moat data and is never published;
 * the mirror is pushed into the private Supabase table new_companies_watchlist by
 * push_new_companies.py (service_role) and read here under the owner's
 * authenticated session, gated by RLS. Owner edits (company URL / careers URL /
 * sector) are written to new_companies_annotations (owner-write RLS) and OVERLAID
 * onto the mirror row (annotation wins). push_new_companies.py drains those
 * annotations back into the discovery app (POST /api/watchlist/annotate), so the
 * two stores reconcile. Same trust model as js/admin.js: this file is public
 * source, the email check is only UX, the real boundary is the tables' RLS.
 *
 * Self-gates: injects a "New companies" tab (next to About) ONLY when the
 * signed-in Google account is the owner.
 *
 * Everything lives in this file (the js/ dir is published whole) so the
 * binary-mode index.html edit is a single <script> tag.
 */
(function () {
  "use strict";

  var SUPA_URL = "https://pqatrxbwevetcqntpbzk.supabase.co";
  var SUPA_KEY = "sb_publishable_sQ5bgIPHepLVW0Bw49W1WQ_G9rLjjSb";
  var OWNER_EMAIL = "sotnik@gmail.com";
  var TABLE = "new_companies_watchlist";
  var ANN_TABLE = "new_companies_annotations";
  var DISM_TABLE = "new_companies_dismissed";
  var FO_TABLE = "new_companies_founder_overrides";  // owner's local founder edits

  // Known tech-company sectors — mirrors the discovery classifier taxonomy
  // (src/pipeline/rules/sector-taxonomy.json). Keep the two in sync.
  var SECTORS = [
    "Healthcare Tech", "Fintech", "Cybersecurity", "AgriTech", "Mobility",
    "Enterprise SaaS", "FoodTech", "CleanTech / Energy", "E-commerce / Retail",
    "Gaming / Media", "Other",
  ];

  var AC = (typeof _supa !== "undefined" && _supa) ||
           (window.supabase && window.supabase.createClient(SUPA_URL, SUPA_KEY));
  if (!AC) return;

  var loaded = false;
  var rows = [];             // mirror rows
  var ann = {};              // chp -> {company_url, careers_url, sector, linkedin_url}
  var dismissed = {};        // chp -> true (companies the owner removed)
  var foverride = {};        // chp -> string ('' = owner cleared) ; absent = use machine founder
  var view = "new";          // "new" = companies WITH a confirmed site ; "watch" = still waiting
  var showDismissed = false; // include removed companies in the view
  var needsUrlOnly = false;  // show only rows with no confirmed URL
  var founderOnly = false;   // show only rows founder_recon has surfaced a founder for
  var editChp = null;        // chp currently being edited
  var busyChp = null;        // chp with an in-flight save
  var pendingAccept = null;  // {chp, company_url?, linkedin_url?} — a candidate the
                             // owner clicked Accept on, prefilled into the edit form
                             // (never auto-saved; the owner still presses Save).
  var sortKey = null;        // 'name_en'|'chp'|'incorporation_date'|'age_months'|'sector'|'company_url'|'careers_url'
  var sortDir = 1;           // 1 asc, -1 desc
  var selected = {};         // chp -> true (rows ticked for a bulk remove)

  var COLLATOR = new Intl.Collator(["he", "en"], { numeric: true, sensitivity: "base" });

  // ── auth gate ──────────────────────────────────────────────────────────────
  function isOwner(user) {
    return user && (user.email || "").toLowerCase() === OWNER_EMAIL;
  }
  AC.auth.getSession().then(function (res) {
    var user = res && res.data && res.data.session && res.data.session.user;
    if (isOwner(user)) injectTab();
  });
  AC.auth.onAuthStateChange(function (_e, session) {
    if (session && isOwner(session.user)) injectTab();
    else removeTab();
  });

  // ── helpers ──────────────────────────────────────────────────────────────────
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtLocation(r) {
    var streetLine = [r.street, r.house_number].filter(function (p) { return p && String(p).trim(); }).join(" ");
    var parts = [r.city, streetLine].filter(function (p) { return p && String(p).trim(); });
    return parts.length ? parts.join(" · ") : "—";
  }
  function withScheme(v) {
    var s = (v == null ? "" : String(v)).trim();
    return s && !/^https?:\/\//i.test(s) ? "https://" + s : s;
  }
  // Effective value of a row after overlaying the owner's annotation (ann wins).
  function eff(r) {
    var a = ann[r.chp] || {};
    var fo = foverride[r.chp];  // undefined = no override; '' = owner cleared; else the name
    return {
      chp: r.chp, name_en: r.name_en, name_tm: r.name_tm,
      incorporation_date: r.incorporation_date, founded_year: r.founded_year,
      age_months: r.age_months, city: r.city, street: r.street, house_number: r.house_number,
      sector: a.sector != null ? a.sector : r.sector,
      company_url: a.company_url != null ? a.company_url : r.company_url,
      careers_url: a.careers_url != null ? a.careers_url : r.careers_url,
      linkedin_url: a.linkedin_url != null ? a.linkedin_url : r.linkedin_url,
      company_url_manual: a.company_url != null || r.company_url_manual,
      careers_url_manual: a.careers_url != null || r.careers_url_manual,
      linkedin_url_manual: a.linkedin_url != null,
      sector_manual: a.sector != null || r.sector_manual,
      // Enricher proposals (never overlaid by an annotation — kept as pure hints).
      linkedin_url_candidate: r.linkedin_url_candidate,
      company_url_candidate: r.company_url_candidate,
      sector_candidate: r.sector_candidate,
      candidate_confidence: r.candidate_confidence,
      candidate_source: r.candidate_source,
      // founder_recon write-back — WHO is behind the company + the attribution's
      // provenance tier. The owner's LOCAL edit (foverride) wins when present: a
      // non-empty string replaces the name (tier→OWNER), '' hides the machine name.
      // Absent override = the machine value unchanged (still waiting on a run if empty).
      founders: fo !== undefined ? fo : r.founders,
      founder_tier: fo ? "OWNER" : (fo === "" ? null : r.founder_tier),
      founder_terminal_state: fo !== undefined ? null : r.founder_terminal_state,
      founder_source: fo !== undefined ? "owner" : r.founder_source,
      founder_checked_at: fo !== undefined ? null : r.founder_checked_at,
      founder_owner_edited: fo !== undefined,   // true once the owner touched it
      founder_machine: r.founders,              // the untouched founder_recon value
    };
  }
  // A row "has founder details" once founder_recon surfaced a name for it. Rows
  // without are the ones still waiting for the next autopilot run.
  function hasFounder(r) { return !!(r.founders && String(r.founders).trim()); }
  // A row has "details" — the New-companies cohort — once its own company website is
  // confirmed. LinkedIn alone is not a site, so this is company_url only (owner choice).
  // Rows without stay in the Watchlist cohort, waiting for the next enrichment run.
  function hasSite(r) { return !!(r.company_url && String(r.company_url).trim()); }
  // A row still "needs a URL" when the owner has confirmed none of company /
  // careers / linkedin — that is what the enricher's suggestions are for.
  function needsUrl(r) { return !r.company_url && !r.careers_url && !r.linkedin_url; }
  // Sort weight for the Suggested column: high > medium > (has a candidate) > none.
  function candidateRank(r) {
    if (r.candidate_confidence === "high") return 3;
    if (r.candidate_confidence === "medium") return 2;
    if (r.company_url_candidate || r.linkedin_url_candidate) return 1;
    return 0;
  }
  function shortUrl(u) {
    return String(u == null ? "" : u).replace(/^https?:\/\//i, "").replace(/\/+$/, "");
  }
  function link(url, manual) {
    if (!url) return "—";
    return '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer" title="' +
      esc(url) + (manual ? " (added by you)" : " (techmap hint)") +
      '" style="color:var(--accent);display:inline-block;max-width:14rem;overflow:hidden;' +
      'text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom;">' + esc(shortUrl(url)) + "</a>";
  }
  function extLink(href, label, title) {
    return '<a href="' + esc(href) + '" target="_blank" rel="noopener noreferrer" title="' + esc(title) +
      '" style="color:var(--ink-faint);text-decoration:none;font-size:11px;white-space:nowrap;">' + label + "</a>";
  }
  // Zero-risk manual shortcuts for a URL-less row (plan Phase 4). Just links —
  // they open a search in a new tab, they never write anything.
  function manualLinks(r) {
    var name = (r.name_en || "").replace(/\s+(LTD|LTD\.|LIMITED)\s*$/i, "").trim();
    var g = "https://www.google.com/search?q=" + encodeURIComponent('"' + name + '" Israel careers');
    var li = "https://www.google.com/search?q=" + encodeURIComponent("site:linkedin.com/company " + name);
    var gov = "https://www.google.com/search?q=" + encodeURIComponent(r.chp + " רשם החברות");
    return '<span style="display:inline-flex;gap:8px;">' +
      extLink(g, "🔍 Google", "Search: " + name + " Israel careers") +
      extLink(li, "in", "Find on LinkedIn") +
      extLink(gov, "gov.il", "ح.פ. " + (r.chp || "") + " in the companies registry") +
      "</span>";
  }
  function confBadge(conf) {
    if (conf !== "high" && conf !== "medium") return "";
    var hi = conf === "high";
    var bg = hi ? "rgba(34,160,90,0.16)" : "rgba(200,140,20,0.16)";
    var fg = hi ? "#1f9d57" : "#b8860b";
    return '<span title="' + (hi ? "Israel-corroborated (country/city match)" : "name-only match — likely namesake, verify") +
      '" style="display:inline-block;padding:1px 6px;border-radius:999px;font-size:10px;font-weight:700;' +
      'background:' + bg + ";color:" + fg + ';text-transform:uppercase;letter-spacing:0.03em;">' + esc(conf) + "</span>";
  }
  // The Suggested cell for a non-edit row: a confidence badge + Accept chips that
  // open the edit form prefilled (owner still saves), plus manual shortcuts.
  // The Sector cell: a confirmed sector wins; otherwise the enricher's suggestion
  // (from the LinkedIn industry) is shown inline with a one-click Apply that saves
  // it directly (no editor round-trip), preserving any confirmed URLs.
  function sectorCell(r) {
    // A registry/classifier "Other" is a non-answer, so a specific enricher
    // suggestion should still surface — unless the owner deliberately chose the
    // sector (sector_manual). Empty or an un-owned "Other" counts as "not set".
    var weak = (!r.sector || r.sector === "Other") && !r.sector_manual;
    if (r.sector && !weak) return esc(r.sector);
    if (weak && r.sector_candidate) {
      var busy = busyChp === r.chp;
      var cur = r.sector
        ? '<span style="color:var(--ink-faint);font-size:11px;">(' + esc(r.sector) + ") </span>" : "";
      return cur +
        '<span style="color:var(--ink-faint);font-style:italic;" title="Suggested from the LinkedIn industry">' +
        esc(r.sector_candidate) + "</span> " +
        '<button data-act="apply-sector" data-chp="' + esc(r.chp) + '"' + (busy ? " disabled" : "") +
        ' title="Apply this sector" style="margin-top:3px;padding:1px 7px;border:1px solid var(--rule);' +
        'border-radius:999px;background:var(--panel);color:var(--accent);font-size:11px;font-weight:600;cursor:pointer;">' +
        (busy ? "…" : "Apply") + "</button>";
    }
    return r.sector ? esc(r.sector) : "—";
  }
  function suggestCell(r) {
    if (!needsUrl(r)) {
      return '<span style="color:var(--ink-faint);font-size:11px;">✓ set</span>';
    }
    var bits = [];
    var hasCand = r.company_url_candidate || r.linkedin_url_candidate;
    if (hasCand) {
      bits.push(confBadge(r.candidate_confidence));
      if (r.company_url_candidate) {
        bits.push('<button data-act="accept-web" data-chp="' + esc(r.chp) + '" title="Accept ' +
          esc(r.company_url_candidate) + ' as the company URL (opens the editor to confirm)"' +
          ' style="padding:2px 7px;border:1px solid var(--rule);border-radius:999px;background:var(--panel);' +
          'color:var(--accent);font-size:11px;font-weight:600;cursor:pointer;max-width:11rem;overflow:hidden;' +
          'text-overflow:ellipsis;white-space:nowrap;">+ ' + esc(shortUrl(r.company_url_candidate)) + "</button>");
      }
      if (r.linkedin_url_candidate) {
        bits.push('<button data-act="accept-li" data-chp="' + esc(r.chp) + '" title="Accept ' +
          esc(r.linkedin_url_candidate) + ' as the LinkedIn URL (opens the editor to confirm)"' +
          ' style="padding:2px 7px;border:1px solid var(--rule);border-radius:999px;background:var(--panel);' +
          'color:var(--accent);font-size:11px;font-weight:600;cursor:pointer;">+ in</button>');
      }
    }
    bits.push(manualLinks(r));
    return '<div style="display:flex;flex-direction:column;gap:5px;align-items:flex-start;">' + bits.join("") + "</div>";
  }

  // Provenance-tier badge for a founder_recon attribution. FACT (two independent
  // origins) is the only "confirmed" green; INFERENCE is a reasoned link; a name off
  // the company's own site alone is SELF_ATTESTED; a single press lead is UNVERIFIED.
  // The colour ladder mirrors that honesty gate so the tab never over-claims.
  function tierBadge(tier) {
    var t = String(tier || "").toUpperCase();
    var map = {
      FACT:          { bg: "rgba(34,160,90,0.16)",  fg: "#1f9d57", tip: "Two independent origins agree" },
      INFERENCE:     { bg: "rgba(52,120,210,0.16)", fg: "#2f6fd0", tip: "A reasoned link from evidence" },
      SELF_ATTESTED: { bg: "rgba(200,140,20,0.16)", fg: "#b8860b", tip: "The company's own site alone — not corroborated" },
      UNVERIFIED:    { bg: "rgba(140,140,150,0.16)", fg: "#7a7a86", tip: "A single unconfirmed lead (e.g. press)" },
      OWNER:         { bg: "rgba(124,92,208,0.16)",  fg: "#7c5cd0", tip: "Edited by you — overrides the machine attribution" },
    };
    var s = map[t];
    if (!s) return "";
    return '<span title="' + esc(s.tip) + '" style="display:inline-block;padding:1px 6px;border-radius:999px;' +
      "font-size:10px;font-weight:700;background:" + s.bg + ";color:" + s.fg + ';text-transform:uppercase;' +
      'letter-spacing:0.03em;white-space:nowrap;">' + esc(t.replace(/_/g, " ")) + "</span>";
  }

  // The Founder cell: the surfaced name(s) + a provenance-tier badge. A row with no
  // founder yet shows a muted "waiting" hint (the next autopilot run may fill it).
  function founderCell(r) {
    if (!hasFounder(r)) {
      // Owner cleared it: say so (and keep the machine value in the tooltip) rather
      // than the generic "waiting" hint, which would wrongly read as never-attributed.
      if (r.founder_owner_edited) {
        var was = r.founder_machine ? " · was: " + r.founder_machine : "";
        return '<span style="color:var(--ink-faint);font-size:11px;" title="You cleared this founder' +
          esc(was) + '">— <em>hidden</em></span>';
      }
      return '<span style="color:var(--ink-faint);font-size:11px;" title="No free founder attributed yet — ' +
        'waiting for the next enrichment run">—</span>';
    }
    var title, badge;
    if (r.founder_owner_edited) {
      title = "Edited by you" + (r.founder_machine ? " · machine value was: " + r.founder_machine : "");
      badge = tierBadge("OWNER");
    } else {
      var when = r.founder_checked_at ? new Date(r.founder_checked_at).toLocaleDateString() : "";
      var srcNote = r.founder_source === "founder_recon_press" ? "press lead" : "founder_recon";
      title = srcNote + (r.founder_terminal_state ? " · " + r.founder_terminal_state : "") + (when ? " · " + when : "");
      badge = tierBadge(r.founder_tier);
    }
    return '<div title="' + esc(title) + '" style="display:flex;flex-direction:column;gap:3px;align-items:flex-start;">' +
      "<span>" + esc(r.founders) + "</span>" + badge + "</div>";
  }

  // ── tab + panel ──────────────────────────────────────────────────────────────
  var OTHER_BTNS = ["vbtnJobs", "vbtnApps", "vbtnAnalytics", "vbtnAbout"];

  function injectTab() {
    if (document.getElementById("vbtnNewCompanies")) return;
    var bar = document.querySelector(".view-toggle");
    var about = document.getElementById("vbtnAbout");
    if (!bar || !about) { return void setTimeout(injectTab, 400); }

    var btn = document.createElement("button");
    btn.className = "vbtn";
    btn.id = "vbtnNewCompanies";
    btn.innerHTML = "🆕 New companies";
    btn.addEventListener("click", openTab);
    about.insertAdjacentElement("afterend", btn);

    buildPanel();
    OTHER_BTNS.forEach(function (id) {
      var b = document.getElementById(id);
      if (b) b.addEventListener("click", closeTab);
    });
  }
  function removeTab() {
    var b = document.getElementById("vbtnNewCompanies");
    if (b) b.remove();
    var p = document.getElementById("newCompaniesPanel");
    if (p) p.style.display = "none";
  }

  function buildPanel() {
    if (document.getElementById("newCompaniesPanel")) return;
    var panel = document.createElement("div");
    panel.id = "newCompaniesPanel";
    panel.style.cssText = "display:none;padding:32px 48px 64px;";
    panel.innerHTML =
      '<div style="max-width:1200px;">' +
        '<h2 style="font-size:1.5rem;margin-bottom:0.5rem;border-bottom:2px solid var(--rule);' +
          'padding-bottom:0.5rem;color:var(--ink);">🆕 New companies</h2>' +
        '<p style="color:var(--ink-dim);font-size:14px;line-height:1.5;margin-bottom:16px;">' +
          "Private watchlist: eligible new Israeli tech companies that JobFinder does not yet track " +
          "and that have no scrapable ATS. Owner-only. The <strong>Suggested</strong> column proposes a " +
          "LinkedIn / website found by the enricher — a green <em>high</em> badge is Israel-corroborated, " +
          "amber <em>medium</em> is a name-only match to verify. Click a suggestion (or use the 🔍 links) " +
          "then <strong>Edit</strong> to confirm the company URL, careers URL, LinkedIn and sector — saved " +
          "here and synced back into the discovery app on the next <code>push_new_companies.py</code>." +
        "</p>" +
        // Two cohorts of the same watchlist, split by whether the company site is
        // confirmed: "New companies" = has a site (details in hand), "Watchlist" =
        // still waiting. A segmented control, not two separate URLs.
        '<div id="ncViewTabs" role="tablist" style="display:inline-flex;gap:4px;margin-bottom:14px;' +
          'border:1px solid var(--rule);border-radius:8px;padding:3px;background:var(--panel);">' +
          '<button id="ncViewNew" role="tab" data-view="new" style="padding:7px 16px;border:0;' +
            'border-radius:6px;background:transparent;color:var(--ink);font-size:13px;font-weight:700;' +
            'cursor:pointer;" title="Companies whose website is confirmed">🆕 New companies</button>' +
          '<button id="ncViewWatch" role="tab" data-view="watch" style="padding:7px 16px;border:0;' +
            'border-radius:6px;background:transparent;color:var(--ink);font-size:13px;font-weight:700;' +
            'cursor:pointer;" title="Companies still waiting for a confirmed website">📋 Watchlist</button>' +
        "</div>" +
        '<p id="ncViewHint" style="margin:-6px 0 14px;font-size:12.5px;color:var(--ink-faint);"></p>' +
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-bottom:14px;">' +
          '<input id="ncSearch" type="search" placeholder="Search name, corporate_id or city…" ' +
            'style="flex:1 1 16rem;min-width:12rem;padding:8px 12px;border:1px solid var(--rule);' +
            'border-radius:4px;background:var(--panel);color:var(--ink);font-size:14px;" />' +
          '<span id="ncCount" style="font-size:13px;color:var(--ink-faint);"></span>' +
          '<button id="ncNeedsUrl" style="padding:6px 12px;border:1px solid var(--rule);border-radius:4px;' +
            'background:var(--panel);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;" ' +
            'title="Show only companies with no confirmed URL yet">Needs URL</button>' +
          '<button id="ncHasFounder" style="padding:6px 12px;border:1px solid var(--rule);border-radius:4px;' +
            'background:var(--panel);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;" ' +
            'title="Show only companies a founder was surfaced for">Has founder</button>' +
          '<button id="ncShowDism" style="padding:6px 12px;border:1px solid var(--rule);border-radius:4px;' +
            'background:var(--panel);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;">' +
            "Show removed</button>" +
          '<button id="ncBulkRemove" disabled style="padding:6px 12px;border:1px solid var(--accent-2);border-radius:4px;' +
            'background:var(--panel);color:var(--accent-2);font-size:13px;font-weight:600;cursor:pointer;" ' +
            'title="Remove every ticked company from the watchlist">Remove selected</button>' +
          '<button id="ncExport" style="padding:6px 12px;border:1px solid var(--rule);border-radius:4px;' +
            'background:var(--panel);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;">' +
            "Export CSV</button>" +
          '<button id="ncRefresh" style="padding:6px 12px;border:1px solid var(--rule);border-radius:4px;' +
            'background:var(--panel);color:var(--ink);font-size:13px;font-weight:600;cursor:pointer;">' +
            "Refresh</button>" +
        "</div>" +
        '<p id="ncActionError" role="alert" style="display:none;margin:0 0 10px;color:var(--accent-2);font-size:13px;"></p>' +
        '<div id="ncBody"></div>' +
        '<p id="ncFooter" style="margin-top:14px;font-size:12px;color:var(--ink-faint);"></p>' +
      "</div>";
    var anchor = document.getElementById("aboutPanel") || document.body;
    anchor.insertAdjacentElement("afterend", panel);

    panel.querySelector("#ncRefresh").addEventListener("click", function () { load(true); });
    panel.querySelector("#ncSearch").addEventListener("input", render);
    panel.querySelector("#ncExport").addEventListener("click", exportCsv);
    panel.querySelector("#ncShowDism").addEventListener("click", function () {
      showDismissed = !showDismissed; render();
    });
    panel.querySelector("#ncViewNew").addEventListener("click", function () { setView("new"); });
    panel.querySelector("#ncViewWatch").addEventListener("click", function () { setView("watch"); });
    panel.querySelector("#ncNeedsUrl").addEventListener("click", function () {
      needsUrlOnly = !needsUrlOnly; render();
    });
    panel.querySelector("#ncHasFounder").addEventListener("click", function () {
      founderOnly = !founderOnly; render();
    });
    panel.querySelector("#ncBulkRemove").addEventListener("click", function () { void bulkDismiss(); });
    // Event delegation for the sortable headers + per-row Edit/Save/Cancel/Remove.
    panel.querySelector("#ncBody").addEventListener("click", onBodyClick);
    // Delegation for the select-all + per-row selection checkboxes.
    panel.querySelector("#ncBody").addEventListener("change", onBodyChange);
  }

  function openTab() {
    OTHER_BTNS.forEach(function (id) {
      var b = document.getElementById(id);
      if (b) b.classList.remove("active");
    });
    document.getElementById("vbtnNewCompanies").classList.add("active");
    var main = document.querySelector("main"); if (main) main.style.display = "none";
    var st = document.querySelector(".status"); if (st) st.style.display = "none";
    ["analyticsPanel", "appsPanel", "aboutPanel"].forEach(function (id) {
      var p = document.getElementById(id); if (p) p.style.display = "none";
    });
    document.getElementById("newCompaniesPanel").style.display = "block";
    if (!loaded) load(false);
  }
  function closeTab() {
    var p = document.getElementById("newCompaniesPanel");
    if (p) p.style.display = "none";
    var b = document.getElementById("vbtnNewCompanies");
    if (b) b.classList.remove("active");
  }

  // Switch cohort (New companies ↔ Watchlist). Clears any in-flight edit/selection
  // so state from one cohort never leaks into the other.
  function setView(v) {
    if (view === v) return;
    view = v;
    selected = {};
    editChp = null;
    render();
  }

  // Paint one cohort tab: filled when active, ghosted when not; label carries a count.
  function styleViewTab(id, active, label, n) {
    var b = document.getElementById(id);
    if (!b) return;
    b.textContent = label + (n ? " (" + n + ")" : "");
    b.style.background = active ? "var(--ink)" : "transparent";
    b.style.color = active ? "#fff" : "var(--ink-dim)";
    b.setAttribute("aria-selected", active ? "true" : "false");
  }

  // ── data ─────────────────────────────────────────────────────────────────────
  async function load(force) {
    var body = document.getElementById("ncBody");
    var footer = document.getElementById("ncFooter");
    if (force) loaded = false;
    editChp = null;
    selected = {};
    body.innerHTML = '<p style="color:var(--ink-faint);">Loading…</p>';
    try {
      var mirror = await AC.from(TABLE)
        .select("*").order("age_months", { ascending: true, nullsFirst: false });
      if (mirror.error) throw mirror.error;
      var a = await AC.from(ANN_TABLE).select("*");
      if (a.error) throw a.error;
      var dm = await AC.from(DISM_TABLE).select("chp");
      if (dm.error) throw dm.error;
      rows = mirror.data || [];
      ann = {};
      (a.data || []).forEach(function (x) {
        ann[x.chp] = {
          company_url: x.company_url, careers_url: x.careers_url,
          sector: x.sector, linkedin_url: x.linkedin_url,
        };
      });
      dismissed = {};
      (dm.data || []).forEach(function (x) { dismissed[x.chp] = true; });
      // Owner's local founder edits. Loaded defensively: before the one-time SQL
      // migration adds this table the select 404s — the tab must still work, just
      // without overrides, so a failure here is swallowed rather than breaking load.
      foverride = {};
      try {
        var fo = await AC.from(FO_TABLE).select("chp,founder");
        if (!fo.error) {
          (fo.data || []).forEach(function (x) {
            foverride[x.chp] = x.founder == null ? "" : String(x.founder);
          });
        }
      } catch (_e) { /* table not migrated yet — overrides unavailable */ }
      loaded = true;
      var latest = rows.reduce(function (m, x) {
        return x.snapshot_at && x.snapshot_at > m ? x.snapshot_at : m;
      }, "");
      footer.textContent = latest ? "Mirrored " + new Date(latest).toLocaleString() : "";
      render();
    } catch (e) {
      body.innerHTML = '<p style="color:var(--accent-2);">Could not load the watchlist: ' +
        esc(e.message || e) + "</p>";
    }
  }

  function showActionError(msg) {
    var el = document.getElementById("ncActionError");
    if (!el) return;
    if (msg) { el.textContent = msg; el.style.display = "block"; }
    else { el.textContent = ""; el.style.display = "none"; }
  }

  function onBodyClick(e) {
    var t = e.target;
    var th = t && t.closest ? t.closest("th[data-sort]") : null;
    if (th) { toggleSort(th.getAttribute("data-sort")); return; }
    var btn = t && t.closest ? t.closest("button[data-act]") : null;
    if (!btn) return;
    var chp = btn.getAttribute("data-chp");
    if (!chp) return;
    var act = btn.getAttribute("data-act");
    if (act === "edit") { editChp = chp; pendingAccept = null; showActionError(null); render(); }
    else if (act === "cancel") { editChp = null; pendingAccept = null; render(); }
    else if (act === "save") { void save(chp); }
    else if (act === "dismiss") { void dismiss(chp); }
    else if (act === "restore") { void restore(chp); }
    else if (act === "apply-sector") { void applySector(chp); }
    else if (act === "accept-web" || act === "accept-li" || act === "accept-sector") {
      // Copy the candidate into the edit form (owner still presses Save). Merge
      // with any existing pending accept so accepting several chips works.
      var src = null;
      for (var i = 0; i < rows.length; i++) { if (rows[i].chp === chp) { src = rows[i]; break; } }
      var prev = (pendingAccept && pendingAccept.chp === chp) ? pendingAccept : { chp: chp };
      if (act === "accept-web" && src) prev.company_url = src.company_url_candidate || "";
      if (act === "accept-li" && src) prev.linkedin_url = src.linkedin_url_candidate || "";
      if (act === "accept-sector" && src) prev.sector = src.sector_candidate || "";
      pendingAccept = prev;
      editChp = chp; showActionError(null); render();
    }
  }

  // Selection checkboxes: a per-row tick toggles that chp; the header "select all"
  // ticks/unticks every currently-visible, non-removed row at once.
  function onBodyChange(e) {
    var t = e.target;
    if (!t || t.type !== "checkbox") return;
    if (t.id === "ncSelAll") {
      visibleRows().forEach(function (r) {
        if (dismissed[r.chp]) return;
        if (t.checked) selected[r.chp] = true; else delete selected[r.chp];
      });
      render();
      return;
    }
    var chp = t.getAttribute("data-sel");
    if (!chp) return;
    if (t.checked) selected[chp] = true; else delete selected[chp];
    updateBulkButton();
    var sa = document.getElementById("ncSelAll");
    if (sa) syncSelAll(sa);
  }

  function selectedChps() { return Object.keys(selected); }

  function syncSelAll(box) {
    var vis = visibleRows().filter(function (r) { return !dismissed[r.chp]; });
    var n = vis.filter(function (r) { return selected[r.chp]; }).length;
    box.checked = n > 0 && n === vis.length;
    box.indeterminate = n > 0 && n < vis.length;
  }

  function updateBulkButton() {
    var btn = document.getElementById("ncBulkRemove");
    if (!btn) return;
    var n = selectedChps().length;
    btn.disabled = n === 0;
    btn.style.opacity = n === 0 ? "0.55" : "1";
    btn.textContent = n ? "Remove selected (" + n + ")" : "Remove selected";
  }

  // Remove every ticked company in one shot (single upsert of dismissal rows).
  async function bulkDismiss() {
    var chps = selectedChps();
    if (!chps.length) return;
    if (!window.confirm("Remove " + chps.length + " compan" + (chps.length === 1 ? "y" : "ies") +
      " from the watchlist? They will be hidden here (use “Show removed” to restore).")) return;
    var btn = document.getElementById("ncBulkRemove");
    if (btn) btn.disabled = true;
    showActionError(null);
    try {
      var now = new Date().toISOString();
      var payload = chps.map(function (chp) { return { chp: chp, dismissed_at: now }; });
      var u = await AC.from(DISM_TABLE).upsert(payload, { onConflict: "chp" });
      if (u.error) throw u.error;
      chps.forEach(function (chp) {
        dismissed[chp] = true;
        delete selected[chp];
        if (editChp === chp) editChp = null;
      });
    } catch (e) {
      showActionError("Remove failed: " + (e.message || e));
    } finally {
      render();
    }
  }

  function toggleSort(key) {
    if (sortKey === key) sortDir = -sortDir;
    else { sortKey = key; sortDir = 1; }
    render();
  }

  // Effective sort value for a column. "Incorporated" sorts by the ISO
  // incorporation_date (chronological under string compare), falling back to the
  // founded_year when only the year is known; everything else sorts on its own
  // field. age_months is numeric — the collator's numeric mode orders it right.
  function sortVal(r, key) {
    if (key === "incorporation_date")
      return r.incorporation_date || (r.founded_year != null ? String(r.founded_year) : "");
    // Suggested column: rank high>medium>has-candidate>none, so a plain string
    // compare (via the collator) orders them; empty sinks to the bottom.
    if (key === "_cand") { var n = candidateRank(r); return n ? String(9 - n) : ""; }
    return r[key];
  }

  // Sort a copy of the effective rows by the active column. Empty values always
  // sink to the bottom regardless of direction; chp/text use a he+en numeric collator.
  function applySort(arr) {
    if (!sortKey) return arr;
    return arr.slice().sort(function (a, b) {
      var va = sortVal(a, sortKey), vb = sortVal(b, sortKey);
      var ea = va == null || va === "", eb = vb == null || vb === "";
      if (ea && eb) return 0;
      if (ea) return 1;
      if (eb) return -1;
      return COLLATOR.compare(String(va), String(vb)) * sortDir;
    });
  }

  async function dismiss(chp) {
    if (!window.confirm("Remove this company from the watchlist? It will be hidden here " +
      "(use “Show removed” to restore it).")) return;
    busyChp = chp; showActionError(null); render();
    try {
      var u = await AC.from(DISM_TABLE).upsert(
        { chp: chp, dismissed_at: new Date().toISOString() }, { onConflict: "chp" });
      if (u.error) throw u.error;
      dismissed[chp] = true;
      if (editChp === chp) editChp = null;
    } catch (e) {
      showActionError("Remove failed: " + (e.message || e));
    } finally {
      busyChp = null; render();
    }
  }

  async function restore(chp) {
    busyChp = chp; showActionError(null); render();
    try {
      var d = await AC.from(DISM_TABLE).delete().eq("chp", chp);
      if (d.error) throw d.error;
      delete dismissed[chp];
    } catch (e) {
      showActionError("Restore failed: " + (e.message || e));
    } finally {
      busyChp = null; render();
    }
  }

  // Build a CSV of whatever is currently shown (search + sort applied, removed
  // excluded unless "Show removed" is on) and trigger a download.
  function exportCsv() {
    var shown = visibleRows();
    var cols = [
      ["Name", function (r) { return r.name_en; }],
      ["Techmap name", function (r) { return r.name_tm; }],
      ["corporate_id", function (r) { return r.chp; }],
      ["Incorporated", function (r) {
        return r.incorporation_date || (r.founded_year != null ? String(r.founded_year) : "");
      }],
      ["Age (mo)", function (r) { return r.age_months == null ? "" : r.age_months; }],
      ["City", function (r) { return r.city; }],
      ["Street", function (r) { return r.street; }],
      ["House number", function (r) { return r.house_number; }],
      ["Sector", function (r) { return r.sector; }],
      ["Company URL", function (r) { return r.company_url; }],
      ["Careers URL", function (r) { return r.careers_url; }],
      ["LinkedIn URL", function (r) { return r.linkedin_url; }],
      ["Suggested company URL", function (r) { return r.company_url_candidate; }],
      ["Suggested LinkedIn", function (r) { return r.linkedin_url_candidate; }],
      ["Suggested sector", function (r) { return r.sector_candidate; }],
      ["Suggestion confidence", function (r) { return r.candidate_confidence; }],
      ["Founder", function (r) { return r.founders; }],
      ["Founder tier", function (r) { return r.founder_tier; }],
      ["Founder source", function (r) { return r.founder_source; }],
      ["Removed", function (r) { return dismissed[r.chp] ? "yes" : ""; }],
    ];
    function q(v) { return '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"'; }
    var lines = [cols.map(function (c) { return q(c[0]); }).join(",")];
    shown.forEach(function (r) {
      lines.push(cols.map(function (c) { return q(c[1](r)); }).join(","));
    });
    // BOM so Excel reads the Hebrew (company / city names) as UTF-8.
    var blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "new_companies_" + new Date().toISOString().slice(0, 10) + ".csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  // The effective rows to display: search-filtered, removed-filtered, sorted.
  function visibleRows() {
    var q = (document.getElementById("ncSearch").value || "").trim().toLowerCase();
    var effRows = rows.map(eff).filter(function (r) {
      if (!showDismissed && dismissed[r.chp]) return false;
      // Cohort split: New companies = confirmed site; Watchlist = still waiting.
      if (view === "new" && !hasSite(r)) return false;
      if (view === "watch" && hasSite(r)) return false;
      if (needsUrlOnly && !needsUrl(r)) return false;
      if (founderOnly && !hasFounder(r)) return false;
      return true;
    });
    var matched = effRows.filter(function (r) {
      if (!q) return true;
      return (r.name_en && r.name_en.toLowerCase().indexOf(q) >= 0) ||
        (r.name_tm && r.name_tm.toLowerCase().indexOf(q) >= 0) ||
        (r.chp && r.chp.indexOf(q) >= 0) ||
        (r.city && r.city.toLowerCase().indexOf(q) >= 0) ||
        (r.sector && r.sector.toLowerCase().indexOf(q) >= 0) ||
        (r.founders && r.founders.toLowerCase().indexOf(q) >= 0);
    });
    return applySort(matched);
  }

  async function save(chp) {
    var panel = document.getElementById("newCompaniesPanel");
    var company_url = withScheme((panel.querySelector("#ncEditCompany") || {}).value);
    var careers_url = withScheme((panel.querySelector("#ncEditCareers") || {}).value);
    var linkedin_url = withScheme((panel.querySelector("#ncEditLinkedin") || {}).value);
    var sectorEl = panel.querySelector("#ncEditSector");
    var sector = (sectorEl ? sectorEl.value : "").trim();
    busyChp = chp; showActionError(null); render();
    try {
      if (!company_url && !careers_url && !sector && !linkedin_url) {
        var d = await AC.from(ANN_TABLE).delete().eq("chp", chp);
        if (d.error) throw d.error;
        delete ann[chp];
      } else {
        var row = {
          chp: chp,
          company_url: company_url || null,
          careers_url: careers_url || null,
          sector: sector || null,
          linkedin_url: linkedin_url || null,
          updated_at: new Date().toISOString(),
        };
        var u = await AC.from(ANN_TABLE).upsert(row, { onConflict: "chp" });
        if (u.error) throw u.error;
        ann[chp] = {
          company_url: row.company_url, careers_url: row.careers_url,
          sector: row.sector, linkedin_url: row.linkedin_url,
        };
      }
      // Founder override (jobfinder-LOCAL, its own table — never drained to discovery).
      // Compare the typed value against the untouched machine founder: equal ⇒ no
      // override (drop any existing), different (incl. blank to hide a name) ⇒ store it.
      // Wrapped in its own try/catch so a founder-specific failure is reported
      // distinctly (and never silently) even when the URL/sector part succeeded.
      var founderEl = panel.querySelector("#ncEditFounder");
      var src = null;
      for (var i = 0; i < rows.length; i++) { if (rows[i].chp === chp) { src = rows[i]; break; } }
      var machineF = (src && src.founders != null) ? String(src.founders).trim() : "";
      var newF = founderEl ? (founderEl.value || "").trim() : null;
      console.log("[founder-edit]", { chp: chp, foundInput: !!founderEl, machine: machineF,
        typed: newF, existingOverride: foverride[chp] });
      if (founderEl) {
        try {
          if (newF === machineF) {
            if (foverride[chp] !== undefined) {
              var df = await AC.from(FO_TABLE).delete().eq("chp", chp);
              console.log("[founder-edit] delete-override result", df);
              if (df.error) throw df.error;
              delete foverride[chp];
            } else {
              console.log("[founder-edit] typed value equals machine and no override — nothing to write");
            }
          } else {
            var uf = await AC.from(FO_TABLE).upsert(
              { chp: chp, founder: newF, updated_at: new Date().toISOString() }, { onConflict: "chp" });
            console.log("[founder-edit] upsert result", uf);
            if (uf.error) throw uf.error;
            foverride[chp] = newF;
          }
        } catch (fe) {
          console.error("[founder-edit] FAILED", fe);
          showActionError("Founder save failed: " + (fe.message || fe) +
            (fe.code ? " [" + fe.code + "]" : ""));
        }
      } else {
        console.warn("[founder-edit] #ncEditFounder input not found — founder not saved");
      }
      editChp = null; pendingAccept = null;
    } catch (e) {
      showActionError("Save failed: " + (e.message || e));
    } finally {
      busyChp = null;
      render();
    }
  }

  // Apply the suggested sector directly (one click, no editor). Merges onto any
  // existing annotation so a confirmed company/careers/linkedin URL is preserved.
  async function applySector(chp) {
    var src = null;
    for (var i = 0; i < rows.length; i++) { if (rows[i].chp === chp) { src = rows[i]; break; } }
    var sector = src && src.sector_candidate;
    if (!sector) return;
    var a = ann[chp] || {};
    busyChp = chp; showActionError(null); render();
    try {
      var row = {
        chp: chp,
        company_url: a.company_url || null,
        careers_url: a.careers_url || null,
        linkedin_url: a.linkedin_url || null,
        sector: sector,
        updated_at: new Date().toISOString(),
      };
      var u = await AC.from(ANN_TABLE).upsert(row, { onConflict: "chp" });
      if (u.error) throw u.error;
      ann[chp] = { company_url: row.company_url, careers_url: row.careers_url, sector: sector, linkedin_url: row.linkedin_url };
    } catch (e) {
      showActionError("Apply sector failed: " + (e.message || e));
    } finally {
      busyChp = null; render();
    }
  }

  // ── render ─────────────────────────────────────────────────────────────────────
  function sectorSelect(current) {
    var opts = ['<option value="">(none)</option>'];
    var seen = {};
    SECTORS.forEach(function (s) {
      seen[s] = true;
      opts.push('<option value="' + esc(s) + '"' + (s === current ? " selected" : "") + ">" + esc(s) + "</option>");
    });
    // Preserve a pre-existing custom value (e.g. an older free-text sector).
    if (current && !seen[current]) {
      opts.push('<option value="' + esc(current) + '" selected>' + esc(current) + "</option>");
    }
    return '<select id="ncEditSector" style="width:100%;padding:5px 6px;border:1px solid var(--rule);' +
      'border-radius:4px;background:var(--panel);color:var(--ink);font-size:13px;">' + opts.join("") + "</select>";
  }
  function textInput(id, val, ph) {
    return '<input id="' + id + '" type="url" value="' + esc(val || "") + '" placeholder="' + esc(ph) +
      '" style="width:100%;padding:5px 6px;border:1px solid var(--rule);border-radius:4px;' +
      'background:var(--panel);color:var(--ink);font-size:13px;" />';
  }
  // The Founder cell in edit mode: a free-text field prefilled with the current
  // (possibly already-overridden) name. Type to correct it, blank it to hide a wrong
  // machine founder. The edit is saved LOCALLY (never pushed to discovery). When an
  // override differs from the machine value, the machine name is shown underneath.
  function founderInput(r) {
    var cur = r.founders != null ? r.founders : "";
    var note = (r.founder_owner_edited && r.founder_machine && r.founder_machine !== r.founders)
      ? '<div style="margin-top:3px;font-size:10px;color:var(--ink-faint);">machine: ' + esc(r.founder_machine) + "</div>"
      : "";
    return '<input id="ncEditFounder" type="text" value="' + esc(cur) + '" placeholder="founder (blank = hide)" ' +
      'title="Type a name to override, or blank the field to hide a wrong machine founder. Saved locally only." ' +
      'style="width:100%;padding:5px 6px;border:1px solid var(--rule);border-radius:4px;' +
      'background:var(--panel);color:var(--ink);font-size:13px;" />' + note;
  }

  // Columns: [label, sortKey|null, {align}]. sortKey set = clickable header.
  var COLS = [
    ["_sel", null],
    ["Company", "name_en"],
    ["corporate_id", "chp"],
    ["Incorporated", "incorporation_date"],
    ["Age (mo)", "age_months", "right"],
    ["Location", null],
    ["Sector", "sector"],
    ["Company URL", "company_url"],
    ["Careers URL", "careers_url"],
    ["Founder", "founders"],
    ["Suggested", "_cand"],
    ["", null],
  ];
  // Fixed column widths so long URLs no longer stretch the table.
  var COLW = ["3%", "14%", "7%", "7%", "5%", "9%", "8%", "10%", "10%", "11%", "10%", "6%"];

  function render() {
    var body = document.getElementById("ncBody");
    var count = document.getElementById("ncCount");
    var dismBtn = document.getElementById("ncShowDism");
    var shown = visibleRows();
    var nDism = Object.keys(dismissed).length;

    // Cohort tabs: live counts + active styling + a one-line hint for the view.
    var effAll = rows.map(eff);
    var nNew = effAll.filter(function (r) { return !dismissed[r.chp] && hasSite(r); }).length;
    var nWatch = effAll.filter(function (r) { return !dismissed[r.chp] && !hasSite(r); }).length;
    styleViewTab("ncViewNew", view === "new", "🆕 New companies", nNew);
    styleViewTab("ncViewWatch", view === "watch", "📋 Watchlist", nWatch);
    var hint = document.getElementById("ncViewHint");
    if (hint) {
      hint.textContent = view === "new"
        ? "Companies whose website is confirmed — the details are in. Edit a row to correct its founder."
        : "Still waiting for a confirmed website. They move to New companies once a site is set.";
    }

    if (dismBtn) {
      dismBtn.textContent = showDismissed ? "Hide removed" : ("Show removed" + (nDism ? " (" + nDism + ")" : ""));
      dismBtn.style.opacity = nDism || showDismissed ? "1" : "0.55";
    }
    var needsBtn = document.getElementById("ncNeedsUrl");
    if (needsBtn) {
      var nNeeds = rows.map(eff).filter(function (r) { return !dismissed[r.chp] && needsUrl(r); }).length;
      needsBtn.textContent = needsUrlOnly ? "Show all" : ("Needs URL" + (nNeeds ? " (" + nNeeds + ")" : ""));
      needsBtn.style.background = needsUrlOnly ? "var(--ink)" : "var(--panel)";
      needsBtn.style.color = needsUrlOnly ? "#fff" : "var(--ink)";
    }
    var foundBtn = document.getElementById("ncHasFounder");
    if (foundBtn) {
      var nFound = rows.map(eff).filter(function (r) { return !dismissed[r.chp] && hasFounder(r); }).length;
      foundBtn.textContent = founderOnly ? "Show all" : ("Has founder" + (nFound ? " (" + nFound + ")" : ""));
      foundBtn.style.background = founderOnly ? "var(--ink)" : "var(--panel)";
      foundBtn.style.color = founderOnly ? "#fff" : "var(--ink)";
    }
    // Total is scoped to the active cohort (not the whole watchlist) so "N of M"
    // reads against the tab the owner is actually looking at.
    var cohortSize = (view === "new" ? nNew : nWatch) + (showDismissed
      ? effAll.filter(function (r) {
          return dismissed[r.chp] && (view === "new" ? hasSite(r) : !hasSite(r));
        }).length
      : 0);
    count.textContent = shown.length === cohortSize
      ? cohortSize + " companies" : shown.length + " of " + cohortSize;

    if (rows.length === 0) {
      body.innerHTML = '<p style="color:var(--ink-faint);padding:16px 0;">No companies in the mirror ' +
        "yet. Run <code>push_new_companies.py</code> with the discovery app running.</p>";
      return;
    }
    if (shown.length === 0) {
      body.innerHTML = '<p style="color:var(--ink-faint);padding:16px 0;">No companies match your search.</p>';
      return;
    }

    var thBase = 'text-align:left;padding:8px 10px;border-bottom:2px solid var(--rule);font-size:11px;' +
      'text-transform:uppercase;letter-spacing:0.03em;color:var(--ink-faint);white-space:nowrap;';
    var td = 'style="padding:8px 10px;border-bottom:1px solid var(--rule);font-size:13px;color:var(--ink);' +
      'vertical-align:top;overflow:hidden;text-overflow:ellipsis;"';

    var cols = COLW.map(function (w) { return '<col style="width:' + w + ';">'; }).join("");
    var heads = COLS.map(function (c) {
      var key = c[1], align = c[2] === "right" ? "text-align:right;" : "";
      if (c[0] === "_sel") {
        return '<th style="' + thBase +
          'text-align:center;"><input type="checkbox" id="ncSelAll" title="Select all shown" ' +
          'style="cursor:pointer;" /></th>';
      }
      if (!key) return '<th style="' + thBase + align + '">' + esc(c[0]) + "</th>";
      var arrow = sortKey === key ? (sortDir === 1 ? " ▲" : " ▼") : "";
      return '<th data-sort="' + key + '" style="' + thBase + align +
        'cursor:pointer;user-select:none;" title="Sort by ' + esc(c[0]) + '">' + esc(c[0]) + arrow + "</th>";
    }).join("");

    var html =
      '<div style="overflow-x:auto;border:1px solid var(--rule);border-radius:4px;background:var(--panel);">' +
      '<table style="width:100%;min-width:60rem;border-collapse:collapse;table-layout:fixed;">' +
      "<colgroup>" + cols + "</colgroup>" +
      "<thead><tr>" + heads + "</tr></thead><tbody>";

    shown.forEach(function (r) {
      var isDism = !!dismissed[r.chp];
      var nameTitle = r.name_tm && r.name_tm !== r.name_en
        ? esc(r.name_en) + " · techmap: " + esc(r.name_tm) : esc(r.name_en);
      var inc = r.incorporation_date || (r.founded_year != null ? String(r.founded_year) : "—");
      // A removed row (or one being edited) can't be ticked for a bulk remove.
      var selCell = (isDism || editChp === r.chp)
        ? "<td " + td + "></td>"
        : "<td " + td + ' style="padding:8px 10px;border-bottom:1px solid var(--rule);text-align:center;">' +
            '<input type="checkbox" data-sel="' + esc(r.chp) + '"' + (selected[r.chp] ? " checked" : "") +
            ' style="cursor:pointer;" /></td>';
      var head = selCell +
        "<td " + td + ' title="' + nameTitle + '"><strong>' + esc(r.name_en) + "</strong>" +
          (isDism ? ' <span style="color:var(--ink-faint);font-weight:400;font-size:11px;">(removed)</span>' : "") + "</td>" +
        "<td " + td + ' title="' + esc(r.chp || "") + '">' + esc(r.chp || "—") + "</td>" +
        "<td " + td + ">" + esc(inc) + "</td>" +
        "<td " + td + ' style="padding:8px 10px;border-bottom:1px solid var(--rule);font-size:13px;text-align:right;">' +
          esc(r.age_months == null ? "—" : r.age_months) + "</td>" +
        "<td " + td + ' title="' + esc(fmtLocation(r)) + '">' + esc(fmtLocation(r)) + "</td>";

      var rowStyle = isDism ? ' style="opacity:0.5;"' : "";

      if (editChp === r.chp) {
        var busy = busyChp === r.chp;
        // A candidate the owner clicked Accept on prefills the matching input;
        // otherwise the input shows the current confirmed value.
        var pa = (pendingAccept && pendingAccept.chp === r.chp) ? pendingAccept : {};
        var coVal = pa.company_url != null ? pa.company_url : r.company_url;
        var liVal = pa.linkedin_url != null ? pa.linkedin_url : r.linkedin_url;
        var secVal = pa.sector != null ? pa.sector : (r.sector || "");
        var showSecChip = (!r.sector || r.sector === "Other") && !r.sector_manual && r.sector_candidate;
        var chips = (needsUrl(r) && (r.company_url_candidate || r.linkedin_url_candidate)) || showSecChip
          ? '<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">' +
              confBadge(r.candidate_confidence) +
              (needsUrl(r) && r.company_url_candidate ? '<button data-act="accept-web" data-chp="' + esc(r.chp) +
                '" style="padding:2px 7px;border:1px solid var(--rule);border-radius:999px;background:var(--panel);' +
                'color:var(--accent);font-size:11px;font-weight:600;cursor:pointer;">use ' + esc(shortUrl(r.company_url_candidate)) + "</button>" : "") +
              (needsUrl(r) && r.linkedin_url_candidate ? '<button data-act="accept-li" data-chp="' + esc(r.chp) +
                '" style="padding:2px 7px;border:1px solid var(--rule);border-radius:999px;background:var(--panel);' +
                'color:var(--accent);font-size:11px;font-weight:600;cursor:pointer;">use LinkedIn</button>' : "") +
              (showSecChip ? '<button data-act="accept-sector" data-chp="' + esc(r.chp) +
                '" style="padding:2px 7px;border:1px dashed var(--rule);border-radius:999px;background:var(--panel);' +
                'color:var(--ink);font-size:11px;font-weight:600;cursor:pointer;">🏷 use ' + esc(r.sector_candidate) + "</button>" : "") +
            "</div>"
          : "";
        html += "<tr>" + head +
          "<td " + td + ' style="overflow:visible;">' + sectorSelect(secVal) + "</td>" +
          "<td " + td + ' style="overflow:visible;">' + textInput("ncEditCompany", coVal, "https://company.com") + "</td>" +
          "<td " + td + ' style="overflow:visible;">' + textInput("ncEditCareers", r.careers_url, "https://…/careers") + "</td>" +
          "<td " + td + ' style="overflow:visible;">' + founderInput(r) + "</td>" +
          "<td " + td + ' style="overflow:visible;">' +
            textInput("ncEditLinkedin", liVal, "https://linkedin.com/company/…") + chips + "</td>" +
          "<td " + td + ' style="white-space:nowrap;">' +
            '<button data-act="save" data-chp="' + esc(r.chp) + '"' + (busy ? " disabled" : "") +
              ' style="padding:4px 9px;border:1px solid var(--ink-faint);border-radius:4px;background:var(--ink);' +
              'color:#fff;font-size:12px;font-weight:700;cursor:pointer;">' + (busy ? "…" : "Save") + "</button> " +
            '<button data-act="cancel" data-chp="' + esc(r.chp) + '"' + (busy ? " disabled" : "") +
              ' style="padding:4px 9px;border:1px solid var(--rule);border-radius:4px;background:var(--panel);' +
              'color:var(--ink-faint);font-size:12px;font-weight:600;cursor:pointer;">Cancel</button>' +
          "</td></tr>";
      } else {
        var busyRow = busyChp === r.chp;
        // When no company URL is confirmed but a LinkedIn one is, show that in the
        // Company URL cell so the row is not blank.
        var coCell = r.company_url ? link(r.company_url, r.company_url_manual)
          : (r.linkedin_url ? link(r.linkedin_url, r.linkedin_url_manual) : "—");
        var actions = isDism
          ? '<button data-act="restore" data-chp="' + esc(r.chp) + '"' + (busyRow ? " disabled" : "") +
              ' style="padding:4px 9px;border:1px solid var(--rule);border-radius:4px;background:var(--panel);' +
              'color:var(--ink);font-size:12px;font-weight:600;cursor:pointer;">' + (busyRow ? "…" : "Restore") + "</button>"
          : '<button data-act="edit" data-chp="' + esc(r.chp) + '"' +
              ' style="padding:4px 9px;border:1px solid var(--rule);border-radius:4px;background:var(--panel);' +
              'color:var(--ink);font-size:12px;font-weight:600;cursor:pointer;">Edit</button> ' +
            '<button data-act="dismiss" data-chp="' + esc(r.chp) + '"' + (busyRow ? " disabled" : "") +
              ' title="Remove from watchlist"' +
              ' style="padding:4px 9px;border:1px solid var(--rule);border-radius:4px;background:var(--panel);' +
              'color:var(--accent-2);font-size:12px;font-weight:600;cursor:pointer;">' + (busyRow ? "…" : "Remove") + "</button>";
        html += "<tr" + rowStyle + ">" + head +
          "<td " + td + ">" + sectorCell(r) + "</td>" +
          "<td " + td + ">" + coCell + "</td>" +
          "<td " + td + ">" + link(r.careers_url, r.careers_url_manual) + "</td>" +
          "<td " + td + ' style="overflow:visible;">' + founderCell(r) + "</td>" +
          "<td " + td + ' style="overflow:visible;">' + suggestCell(r) + "</td>" +
          "<td " + td + ' style="white-space:nowrap;">' + actions + "</td></tr>";
      }
    });
    html += "</tbody></table></div>";
    body.innerHTML = html;

    updateBulkButton();
    var selAll = document.getElementById("ncSelAll");
    if (selAll) syncSelAll(selAll);
  }
})();
