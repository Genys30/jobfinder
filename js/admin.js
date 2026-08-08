/* JobFinder Admin console — owner-only, embedded (no separate URL).
 *
 * Self-gates: mounts the "Admin" button and the console ONLY when the signed-in
 * Google account is the owner. A regular visitor never sees an entry point, and
 * even a direct call to the Edge Functions is rejected server-side by JWT — the
 * email check here is convenience, the real boundary is in supabase/functions/*.
 *
 * Everything lives in this file (the js/ dir is published whole) so the binary-mode
 * index.html edit is a single <script> tag.
 */
(function () {
  "use strict";

  var SUPA_URL = "https://pqatrxbwevetcqntpbzk.supabase.co";
  var SUPA_KEY = "sb_publishable_sQ5bgIPHepLVW0Bw49W1WQ_G9rLjjSb";
  var OWNER_EMAIL = "sotnik@gmail.com";
  var FN = SUPA_URL + "/functions/v1/";

  // Reuse the page's Supabase client if present; else make our own from the CDN
  // global. Either shares the persisted OAuth session in localStorage.
  var AC = (typeof _supa !== "undefined" && _supa) ||
           (window.supabase && window.supabase.createClient(SUPA_URL, SUPA_KEY));
  if (!AC) return; // supabase-js not loaded — nothing to do.

  var built = false;

  // ── auth gate ──────────────────────────────────────────────────────────────
  function isOwner(user) {
    return user && (user.email || "").toLowerCase() === OWNER_EMAIL;
  }

  AC.auth.getSession().then(function (res) {
    var user = res && res.data && res.data.session && res.data.session.user;
    if (isOwner(user)) injectButton();
  });
  AC.auth.onAuthStateChange(function (_e, session) {
    if (session && isOwner(session.user)) injectButton();
    else removeButton();
  });

  function injectButton() {
    if (document.getElementById("_adminBtn")) return;
    var eyebrow = document.querySelector(".eyebrow");
    if (!eyebrow) { return void setTimeout(injectButton, 400); }
    var btn = document.createElement("button");
    btn.id = "_adminBtn";
    btn.textContent = "⚙ Admin";
    btn.style.cssText =
      'font-family:"JetBrains Mono",monospace;font-size:10px;letter-spacing:.12em;' +
      "text-transform:uppercase;background:#1f1b12;border:1px solid #c97f0c;color:#e8b25a;" +
      "padding:3px 10px;border-radius:3px;cursor:pointer;white-space:nowrap;margin-left:8px;";
    btn.onclick = openConsole;
    var rightDiv = eyebrow.querySelector("div");
    (rightDiv || eyebrow).appendChild(btn);
  }
  function removeButton() {
    var b = document.getElementById("_adminBtn");
    if (b) b.remove();
    var c = document.getElementById("adminRoot");
    if (c) c.style.display = "none";
  }

  // ── network helpers ──────────────────────────────────────────────────────────
  async function token() {
    var r = await AC.auth.getSession();
    return r && r.data && r.data.session && r.data.session.access_token;
  }
  async function callFn(name, opts) {
    opts = opts || {};
    var t = await token();
    var headers = { Authorization: "Bearer " + t, apikey: SUPA_KEY };
    if (opts.body) headers["Content-Type"] = "application/json";
    var res = await fetch(FN + name, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    var j = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(j.error || ("HTTP " + res.status));
    return j;
  }

  // ── console shell ────────────────────────────────────────────────────────────
  var TABS = ["Overview", "Sources", "Actions", "Configs", "Logs", "Users"];

  function openConsole() {
    if (!built) buildShell();
    var root = document.getElementById("adminRoot");
    root.style.display = "block";
    selectTab("Overview");
  }

  function buildShell() {
    built = true;
    injectStyles();
    var root = document.getElementById("adminRoot");
    if (!root) {
      root = document.createElement("div");
      root.id = "adminRoot";
      document.body.appendChild(root);
    }
    root.innerHTML =
      '<div class="adm-overlay"><div class="adm-panel">' +
      '<div class="adm-head"><span class="adm-title">JobFinder · Admin</span>' +
      '<span class="adm-sub">cycle console — owner only</span>' +
      '<button class="adm-x" id="admClose">✕</button></div>' +
      '<div class="adm-tabs" id="admTabs"></div>' +
      '<div class="adm-body" id="admBody"></div>' +
      "</div></div>";
    var tabs = root.querySelector("#admTabs");
    TABS.forEach(function (name) {
      var b = document.createElement("button");
      b.className = "adm-tab";
      b.dataset.tab = name;
      b.textContent = name;
      b.onclick = function () { selectTab(name); };
      tabs.appendChild(b);
    });
    root.querySelector("#admClose").onclick = function () { root.style.display = "none"; };
    root.querySelector(".adm-overlay").addEventListener("click", function (e) {
      if (e.target === this) root.style.display = "none";
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && root.style.display !== "none") root.style.display = "none";
    });
  }

  function selectTab(name) {
    Array.prototype.forEach.call(document.querySelectorAll(".adm-tab"), function (t) {
      t.classList.toggle("on", t.dataset.tab === name);
    });
    var body = document.getElementById("admBody");
    body.innerHTML = '<div class="adm-loading">Loading ' + name + "…</div>";
    ({
      Overview: renderOverview, Sources: renderSources, Actions: renderActions,
      Configs: renderConfigs, Logs: renderLogs, Users: renderUsers,
    })[name](body);
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  // Humanize a timestamp into "just now / 3m ago / 2h ago / 4d ago".
  // Non-tech operators read elapsed time far faster than a raw ISO string.
  function ago(iso) {
    if (!iso) return "—";
    var ms = Date.now() - new Date(iso).getTime();
    if (isNaN(ms)) return esc(iso);
    if (ms < 0) ms = 0;
    var s = Math.round(ms / 1000);
    if (s < 45) return "just now";
    var m = Math.round(s / 60);
    if (m < 60) return m + "m ago";
    var h = Math.round(m / 60);
    if (h < 24) return h + "h ago";
    return Math.round(h / 24) + "d ago";
  }
  // Turn the internal where-tag into words the operator recognizes.
  function whereLabel(w) {
    return ({ ci: "Cloud", local: "PC", manual: "Manual" })[w] || (w || "—");
  }
  function err(body, e) {
    body.innerHTML = '<div class="adm-err">⚠ Couldn’t load this — ' + esc(e.message || e) +
      '<div class="adm-hint">Try again in a moment. If it says “invalid session”, sign out and ' +
      "back in. If it keeps failing, the admin backend needs attention " +
      "(details: supabase/admin_setup.sql).</div></div>";
  }

  async function latestHealth() {
    var r = await AC.from("pipeline_health").select("*").order("run_at", { ascending: false }).limit(1);
    if (r.error) throw r.error;
    return (r.data && r.data[0]) || null;
  }

  // ── Overview ─────────────────────────────────────────────────────────────────
  async function renderOverview(body) {
    try {
      var row = await latestHealth();
      if (!row) {
        body.innerHTML = '<div class="adm-empty">No health snapshot yet. Run the pipeline ' +
          "(or <code>py push_health.py</code>) once it can reach Supabase.</div>";
        return;
      }
      var rep = row.report || {};
      var meta = rep._meta || {};
      var srcs = rep.sources || [];
      function bucket(where) {
        var g = srcs.filter(function (s) { return s.where === where; });
        var fresh = g.filter(function (s) { return (s.age_days || 0) === 0; }).length;
        return { total: g.length, fresh: fresh };
      }
      var ci = bucket("ci"), local = bucket("local"), man = bucket("manual");
      var overall = (rep.overall || row.overall || "?");
      var nliOld = (meta.nli_age_days || 0) > 8;
      var streaks = meta.alert_streaks || 0;
      var cards = [
        stage("Overall health", overall,
          (row.ok || 0) + " OK · " + (row.warn || 0) + " WARN · " + (row.fail || 0) + " FAIL",
          overall, "Open the Sources tab and tick “problems only” to see what’s wrong."),
        stage("Cloud fetch", ci.fresh + "/" + ci.total + " fresh today", "runs nightly on GitHub",
          ci.fresh === ci.total ? "OK" : "WARN",
          "Some cloud sources didn’t update today — re-run Actions › “Refresh jobs (cloud)”."),
        stage("PC fetch", local.fresh + "/" + local.total + " fresh today", "runs on your PC (run_fetch)",
          local.fresh === local.total ? "OK" : "WARN",
          "Some PC sources are stale — run Actions › “Full local refresh”."),
        stage("Manual sources", man.fresh + "/" + man.total + " fresh today", "LinkedIn · NLI",
          man.fresh === man.total ? "OK" : "WARN",
          "Drop today’s LinkedIn export / re-save NLI, then refresh."),
        stage("Site data", meta.bundle_mb != null ? meta.bundle_mb + " MB" : "—",
          "the file the site reads" + (meta.bundle_date ? " · " + meta.bundle_date : "") + " (jobs_data.json)",
          meta.bundle_mb != null ? "OK" : "WARN",
          "The site data file is missing — run Actions › “Rebuild bundle”."),
        stage("Trend history", meta.history_last || "—", "last day recorded (history.csv)", "OK"),
        stage("NLI freshness", meta.nli_age_days != null ? meta.nli_age_days + "d old" : "—",
          "re-saved by hand on Saturdays", nliOld ? "WARN" : "OK",
          "NLI is over 8 days old — re-save nli_career.html, then Actions › “Refresh NLI”."),
        stage("Source alerts", streaks + " on streak", "sources failing 2+ runs in a row",
          streaks > 0 ? "WARN" : "OK",
          streaks + " source(s) keep failing — check the Sources tab for FAIL rows."),
      ];
      body.innerHTML =
        '<div class="adm-overview-head"><div class="adm-when">snapshot: ' + esc(ago(row.run_at)) +
        " · " + esc(row.run_at) + '</div><button id="admOvRefresh" class="adm-refresh" title="Refresh">↻</button></div>' +
        '<div class="adm-cards">' + cards.join("") + "</div>" +
        '<h4 class="adm-h">Recent GitHub runs</h4><div id="admRuns" class="adm-runs">loading…</div>';
      var ovr = document.getElementById("admOvRefresh");
      if (ovr) ovr.onclick = function () { renderOverview(body); };
      loadRuns();
    } catch (e) { err(body, e); }
  }
  // A card. `hint` is a one-line "what to do" shown only when the card isn't OK, so a
  // non-technical operator always has a next step instead of a bare red box.
  function stage(label, big, sub, status, hint) {
    var cls = status === "OK" ? "ok" : status === "FAIL" ? "fail" : "warn";
    var fix = (hint && status !== "OK")
      ? '<div class="adm-card-fix">→ ' + esc(hint) + "</div>" : "";
    return '<div class="adm-card ' + cls + '"><div class="adm-card-l">' + esc(label) + "</div>" +
      '<div class="adm-card-b">' + esc(big) + '</div><div class="adm-card-s">' + esc(sub) + "</div>" +
      fix + "</div>";
  }
  async function loadRuns() {
    var el = document.getElementById("admRuns");
    try {
      var j = await callFn("admin-github", { method: "GET" });
      el.innerHTML = (j.runs || []).slice(0, 8).map(function (r) {
        var st = r.conclusion || r.status || "";
        var cls = st === "success" ? "ok" : (st === "failure" ? "fail" : "warn");
        return '<div class="adm-run"><span class="pill ' + cls + '">' + esc(st) + "</span>" +
          '<a href="' + esc(r.html_url) + '" target="_blank" rel="noopener">' + esc(r.name) + "</a>" +
          '<span class="adm-run-t">' + esc((r.created_at || "").replace("T", " ").replace("Z", "")) + "</span></div>";
      }).join("") || '<div class="adm-muted">no runs</div>';
    } catch (e) { el.innerHTML = '<div class="adm-muted">runs unavailable: ' + esc(e.message) + "</div>"; }
  }

  // ── Sources ──────────────────────────────────────────────────────────────────
  async function renderSources(body) {
    try {
      var row = await latestHealth();
      var srcs = (row && row.report && row.report.sources) || [];
      body.innerHTML =
        '<div class="adm-filters"><label><input type="checkbox" id="admProblem"> problems only</label>' +
        '<span class="adm-muted">' + srcs.length + " sources <button id=\"admSrcRefresh\" class=\"adm-refresh\" title=\"Refresh\">↻</button></span></div>" +
        '<div class="adm-tablewrap"><table class="adm-table" id="admSrc"><thead><tr>' +
        "<th>Source</th><th>Runs on</th><th>Status</th><th>Rows</th>" +
        '<th title="rows vs. the previous day">Change 24h</th><th>Age</th></tr></thead><tbody></tbody></table></div>';
      var srf = body.querySelector("#admSrcRefresh");
      if (srf) srf.onclick = function () { renderSources(body); };
      var tbody = body.querySelector("#admSrc tbody");
      function draw() {
        var only = body.querySelector("#admProblem").checked;
        var rows = srcs.slice().sort(function (a, b) {
          var rank = { FAIL: 0, WARN: 1, OK: 2 };
          return (rank[a.status] - rank[b.status]) || (b.rows - a.rows);
        });
        tbody.innerHTML = rows.filter(function (s) { return !only || s.status !== "OK"; }).map(function (s) {
          var d = (s.rows || 0) - (s.prev_rows || 0);
          var dcls = d < 0 ? "neg" : d > 0 ? "pos" : "";
          var scls = s.status === "OK" ? "ok" : s.status === "FAIL" ? "fail" : "warn";
          return "<tr><td>" + esc(s.name) + "</td><td>" + esc(whereLabel(s.where)) + "</td>" +
            '<td><span class="pill ' + scls + '">' + esc(s.status) + "</span></td>" +
            "<td>" + esc(s.rows) + '</td><td class="' + dcls + '">' + (d > 0 ? "+" : "") + d + "</td>" +
            "<td>" + esc(s.age_days) + "d</td></tr>";
        }).join("");
      }
      body.querySelector("#admProblem").onchange = draw;
      draw();
    } catch (e) { err(body, e); }
  }

  // ── Actions ──────────────────────────────────────────────────────────────────
  function renderActions(body) {
    body.innerHTML =
      '<h4 class="adm-h">Refresh &amp; publish — runs in the cloud, works from anywhere</h4>' +
      '<div class="adm-btns">' +
      actBtn("fetch_jobs.yml", "Refresh jobs (cloud)") +
      actBtn("publish_site.yml", "Publish site") +
      actBtn("update_history.yml", "Update trend history") +
      "</div>" +
      '<div id="admActMsg" class="adm-msg"></div>' +
      '<h4 class="adm-h">Deeper refresh — runs on your PC</h4>' +
      '<div class="adm-note">These run on your PC through the local agent. If it isn’t running, ' +
      "they wait in the queue below until it is.</div>" +
      '<div class="adm-btns">' +
      locBtn("check_health", "Check health") +
      locBtn("build_bundle", "Rebuild bundle") +
      locBtn("run_fetch", "Full local refresh") +
      locBtn("refresh_nli", "Refresh NLI") +
      "</div><div id=\"admLocMsg\" class=\"adm-msg\"></div>" +
      '<div class="adm-queue-head"><h4 class="adm-h" style="margin-bottom:0">Local command queue</h4>' +
      '<button id="admQueueRefresh" class="adm-refresh" title="Refresh">↻</button></div>' +
      '<div id="admAgentBanner"></div>' +
      '<div id="admQueue" class="adm-muted">loading…</div>';
    Array.prototype.forEach.call(body.querySelectorAll("[data-wf]"), function (b) {
      b.onclick = async function () {
        var msg = document.getElementById("admActMsg");
        msg.textContent = "Dispatching " + b.dataset.wf + "…";
        try {
          await callFn("admin-github", { method: "POST", body: { workflow: b.dataset.wf } });
          msg.innerHTML = '<span class="ok-txt">✓ dispatched ' + esc(b.dataset.wf) +
            "</span> — check the Overview tab for run status.";
        } catch (e) { msg.innerHTML = '<span class="fail-txt">✗ ' + esc(e.message) + "</span>"; }
      };
    });
    Array.prototype.forEach.call(body.querySelectorAll("[data-cmd]"), function (b) {
      b.onclick = async function () {
        var msg = document.getElementById("admLocMsg");
        if (b.dataset.cmd === "run_fetch" &&
            !confirm("Run a full local refresh? It takes about 6 minutes and discards any " +
                     "uncommitted local changes on the PC before it starts. Continue?")) return;
        msg.textContent = "Queuing " + b.dataset.cmd + "…";
        try {
          var r = await AC.from("admin_commands").insert({ action: b.dataset.cmd }).select().single();
          if (r.error) throw r.error;
          msg.innerHTML = '<span class="ok-txt">✓ queued</span> (' + esc(b.dataset.cmd) +
            "). Watch its progress in the queue below.";
          loadQueue();
        } catch (e) { msg.innerHTML = '<span class="fail-txt">✗ ' + esc(e.message) + "</span>"; }
      };
    });
    var rf = document.getElementById("admQueueRefresh");
    if (rf) rf.onclick = loadQueue;
    loadQueue();
  }
  function actBtn(wf, label) { return '<button class="adm-act" data-wf="' + wf + '">' + esc(label) + "</button>"; }
  function locBtn(cmd, label) { return '<button class="adm-act loc" data-cmd="' + cmd + '">' + esc(label) + "</button>"; }

  // How long a command may sit in "queued" before we suspect the local agent is down.
  var AGENT_STALE_MS = 3 * 60 * 1000;
  // The agent beats every ~20s; treat it as online within 90s (≈4 missed beats).
  var AGENT_ONLINE_MS = 90 * 1000;
  // Best-effort heartbeat read. Returns null if the row/table is absent (the SQL
  // hasn't been applied yet) so the banner falls back to the queue heuristic.
  async function readHeartbeat() {
    try {
      var r = await AC.from("admin_agent_status")
        .select("last_seen,hostname,version").eq("id", 1).maybeSingle();
      if (r.error || !r.data) return null;
      return r.data;
    } catch (_e) { return null; }
  }
  async function loadQueue() {
    var host = document.getElementById("admQueue");
    var banner = document.getElementById("admAgentBanner");
    if (!host) return;
    try {
      var qp = AC.from("admin_commands")
        .select("id,action,state,result,created_at")
        .order("created_at", { ascending: false }).limit(8);
      var hbp = readHeartbeat();
      var r = await qp;
      var hb = await hbp;
      if (r.error) throw r.error;
      var rows = r.data || [];
      if (banner) banner.innerHTML = agentBanner(rows, hb);
      if (!rows.length) {
        host.innerHTML = '<div class="adm-muted">No local commands queued yet. ' +
          "Press a blue button above to enqueue one.</div>";
        return;
      }
      host.innerHTML = '<div class="adm-tablewrap"><table class="adm-table"><thead><tr>' +
        "<th>Command</th><th>Status</th><th>When</th><th>Result</th></tr></thead><tbody>" +
        rows.map(function (c) {
          var st = (c.state || "queued").toLowerCase();
          var cls = st === "done" ? "ok" : st === "failed" ? "fail" : "warn";
          var res = c.result ? esc(String(c.result).slice(0, 120)) : "";
          return "<tr><td>" + esc(c.action) + '</td><td><span class="pill ' + cls + '">' +
            esc(st) + "</span></td><td>" + esc(ago(c.created_at)) +
            '</td><td class="adm-qres">' + res + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    } catch (e) {
      host.innerHTML = '<div class="adm-muted">queue unavailable: ' + esc(e.message) + "</div>";
    }
  }
  // Agent liveness. Primary signal is the heartbeat row (reliable); a running
  // command means it's obviously alive; otherwise fall back to the "stuck in
  // queued" heuristic (works even before the heartbeat SQL is applied).
  function agentBanner(rows, hb) {
    var running = rows.some(function (c) { return (c.state || "").toLowerCase() === "running"; });
    if (running) {
      return '<div class="adm-agent ok">● Local agent active — a command is running now.</div>';
    }
    if (hb && hb.last_seen) {
      var age = Date.now() - new Date(hb.last_seen).getTime();
      var host = hb.hostname ? " on " + esc(hb.hostname) : "";
      if (age <= AGENT_ONLINE_MS) {
        return '<div class="adm-agent ok">● Local agent online' + host +
          " — idle, last check " + esc(ago(hb.last_seen)) + ".</div>";
      }
      return '<div class="adm-agent fail">▲ Local agent offline' + host +
        " — last seen " + esc(ago(hb.last_seen)) + ". Start it with " +
        "<code>run_admin_agent.bat</code> to run queued commands.</div>";
    }
    // No heartbeat row (SQL not applied, or never started): infer from the queue.
    var stale = rows.filter(function (c) {
      return (c.state || "queued").toLowerCase() === "queued" &&
             (Date.now() - new Date(c.created_at).getTime()) > AGENT_STALE_MS;
    });
    if (stale.length) {
      return '<div class="adm-agent fail">▲ Local agent may be offline — ' + stale.length +
        " command(s) have been waiting over 3 minutes. Make sure the agent " +
        "is running on your PC (start it with <code>run_admin_agent.bat</code>).</div>";
    }
    var newest = rows[0];
    if (newest && (newest.state || "").toLowerCase() === "queued") {
      return '<div class="adm-agent warn">◐ Waiting for the local agent to pick up the command…</div>';
    }
    return "";
  }

  // ── Configs ──────────────────────────────────────────────────────────────────
  // Groups accepted by build_sources_manifest.py / the reporter. Keep in sync with
  // the _comment in sources_meta.json.
  var CFG_GROUPS = ["Tech", "Academia", "Healthcare", "Finance", "Corporate",
                    "Public", "NGO/Amutot", "Legal", "Other"];
  // Semantic guardrails beyond "is it valid JSON". These mirror the invariants the
  // build/assert steps enforce server-side, so the operator hears about a bad edit
  // here instead of from a broken nightly run.
  function validateConfig(name, obj) {
    var problems = [];
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      return ["Top level must be a JSON object."];
    }
    if (name === "sources_meta") {
      var srcs = obj.sources;
      if (!srcs || typeof srcs !== "object" || Array.isArray(srcs)) {
        return ['Missing a "sources" object.'];
      }
      Object.keys(srcs).forEach(function (k) {
        if (k.charAt(0) === "_") return;
        var v = srcs[k] || {};
        if (!v.group) problems.push('sources.' + k + ': missing "group".');
        else if (CFG_GROUPS.indexOf(v.group) < 0)
          problems.push('sources.' + k + ': group "' + v.group + '" is not one of ' + CFG_GROUPS.join(", ") + ".");
        if (!v.label) problems.push('sources.' + k + ': missing "label".');
      });
    } else if (name === "companies_meta") {
      var rules = obj.rules;
      if (!Array.isArray(rules)) return ['Missing a "rules" array.'];
      rules.forEach(function (r, i) {
        var at = 'rules[' + i + (r && r.value ? ' "' + r.value + '"' : "") + "]";
        if (!r || typeof r !== "object") { problems.push(at + ": not an object."); return; }
        if (r.match !== "exact" && r.match !== "prefix")
          problems.push(at + ': match="' + r.match + '" — only "exact" or "prefix" are allowed ' +
            "(substring/fuzzy would merge distinct employers).");
        if (!r.value) problems.push(at + ': missing "value".');
        if (!r.canonical) problems.push(at + ': missing "canonical".');
        if (!r.source) problems.push(at + ': missing "source" (use "*" for all sources).');
      });
    }
    return problems;
  }
  var DATE_SEMANTICS = ["observed", "posted", "hybrid", "scrape"];
  // A <select> whose only options are the valid values — an invalid choice is
  // unrepresentable, which is stronger than validating free text after the fact.
  function pickSelect(field, options, current, blankLabel) {
    var opts = "";
    if (blankLabel) opts += '<option value="">' + esc(blankLabel) + "</option>";
    var known = options.indexOf(current) >= 0;
    options.forEach(function (o) {
      opts += '<option value="' + esc(o) + '"' + (o === current ? " selected" : "") + ">" + esc(o) + "</option>";
    });
    // Preserve an unexpected existing value rather than silently dropping it.
    if (current && !known) opts += '<option value="' + esc(current) + '" selected>' + esc(current) + " (?)</option>";
    return '<select class="adm-in" data-f="' + field + '">' + opts + "</select>";
  }
  function cfgField(field, value, cls) {
    return '<input class="adm-in ' + (cls || "") + '" data-f="' + field + '" value="' + esc(value || "") + '">';
  }
  function rowVal(tr, f) {
    var el = tr.querySelector('[data-f="' + f + '"]');
    return el ? el.value : "";
  }
  // ---- sources_meta form ----
  function sourceRow(prefix, v) {
    v = v || {};
    return '<tr class="adm-frow" data-kind="source"><td>' + cfgField("prefix", prefix, "narrow") + "</td>" +
      "<td>" + pickSelect("group", CFG_GROUPS, v.group) + "</td>" +
      "<td>" + cfgField("label", v.label, "wide") + "</td>" +
      "<td>" + pickSelect("date_semantics", DATE_SEMANTICS, v.date_semantics, "—") + "</td>" +
      '<td><button class="adm-del adm-rowdel" title="Remove">×</button></td></tr>';
  }
  function sourcesForm(obj) {
    var sources = (obj && obj.sources) || {};
    var rows = Object.keys(sources).filter(function (k) { return k.charAt(0) !== "_"; })
      .map(function (k) { return sourceRow(k, sources[k]); }).join("");
    return '<div class="adm-formhint">One row per scraper. <b>Group</b> is a dropdown so it can’t be mistyped. ' +
      "Adding a source = one new row.</div>" +
      '<div class="adm-tablewrap"><table class="adm-table adm-form"><thead><tr>' +
      "<th>Prefix</th><th>Group</th><th>Label</th><th>Date basis</th><th></th></tr></thead>" +
      '<tbody id="admFormBody">' + rows + "</tbody></table></div>" +
      '<button class="adm-act adm-addrow" data-add="source">+ Add source</button>';
  }
  // ---- companies_meta form ----
  function ruleRow(r) {
    r = r || {};
    return '<tr class="adm-frow" data-kind="rule"><td>' + cfgField("source", r.source || "*", "narrow") + "</td>" +
      "<td>" + pickSelect("match", ["exact", "prefix"], r.match) + "</td>" +
      "<td>" + cfgField("value", r.value) + "</td>" +
      "<td>" + cfgField("canonical", r.canonical) + "</td>" +
      "<td>" + cfgField("note", r.note, "wide") + "</td>" +
      '<td><button class="adm-del adm-rowdel" title="Remove">×</button></td></tr>';
  }
  function companiesForm(obj) {
    var rules = (obj && obj.rules) || [];
    var rows = rules.map(ruleRow).join("");
    return '<div class="adm-formhint">Employer merge rules. <b>Match</b> is exact/prefix only (enforced — ' +
      "substring would merge distinct employers). The English-name map and the distinct-employer guards " +
      "are edited in <b>Raw JSON</b>.</div>" +
      '<div class="adm-tablewrap"><table class="adm-table adm-form"><thead><tr>' +
      "<th>Source</th><th>Match</th><th>Value</th><th>Counts as</th><th>Note</th><th></th></tr></thead>" +
      '<tbody id="admFormBody">' + rows + "</tbody></table></div>" +
      '<button class="adm-act adm-addrow" data-add="rule">+ Add rule</button>';
  }
  function buildForm(name, obj) {
    if (name === "sources_meta") return sourcesForm(obj);
    if (name === "companies_meta") return companiesForm(obj);
    return '<div class="adm-muted">No form for this config — use Raw JSON.</div>';
  }
  // Read the visible form back into the config object, preserving every key the
  // form doesn't expose (comments, display_en, _distinct_employers, …).
  function readForm(name, obj, view) {
    var trs = view.querySelectorAll(".adm-frow");
    if (name === "sources_meta") {
      var src = {};
      Object.keys(obj.sources || {}).forEach(function (k) { if (k.charAt(0) === "_") src[k] = obj.sources[k]; });
      Array.prototype.forEach.call(trs, function (tr) {
        var prefix = rowVal(tr, "prefix").trim();
        if (!prefix) return;
        var o = { group: rowVal(tr, "group"), label: rowVal(tr, "label").trim() };
        var ds = rowVal(tr, "date_semantics");
        if (ds) o.date_semantics = ds;
        src[prefix] = o;
      });
      obj.sources = src;
    } else if (name === "companies_meta") {
      var rules = [];
      Array.prototype.forEach.call(trs, function (tr) {
        var value = rowVal(tr, "value").trim();
        var canonical = rowVal(tr, "canonical").trim();
        if (!value && !canonical) return; // skip a blank row
        var o = { source: rowVal(tr, "source").trim() || "*", match: rowVal(tr, "match"),
                  value: value, canonical: canonical };
        var note = rowVal(tr, "note").trim();
        if (note) o.note = note;
        rules.push(o);
      });
      obj.rules = rules;
    }
    return obj;
  }

  function renderConfigs(body) {
    body.innerHTML =
      '<div class="adm-cfg-pick"><label>Config: <select id="admCfgSel">' +
      '<option value="sources_meta">sources_meta.json</option>' +
      '<option value="companies_meta">companies_meta.json</option></select></label>' +
      '<button id="admCfgLoad" class="adm-act">Load</button>' +
      '<span id="admCfgModes" class="adm-modes" style="display:none">' +
      '<button class="adm-mode on" data-mode="form">Form</button>' +
      '<button class="adm-mode" data-mode="raw">Raw JSON</button></span>' +
      '<button id="admCfgSave" class="adm-act" disabled>Save + commit</button></div>' +
      '<div id="admCfgView" class="adm-cfg-view"><div class="adm-muted">Load a config to edit it.</div></div>' +
      '<div id="admCfgMsg" class="adm-msg"></div>';
    var sel = body.querySelector("#admCfgSel");
    var view = body.querySelector("#admCfgView");
    var modes = body.querySelector("#admCfgModes");
    var save = body.querySelector("#admCfgSave"), msg = body.querySelector("#admCfgMsg");
    var st = { obj: null, name: null, mode: "form" };

    function render() {
      if (st.mode === "raw") {
        view.innerHTML = '<textarea id="admCfgRaw" class="adm-textarea" spellcheck="false"></textarea>';
        view.querySelector("#admCfgRaw").value = JSON.stringify(st.obj, null, 2);
      } else {
        view.innerHTML = buildForm(st.name, st.obj);
        var addBtn = view.querySelector(".adm-addrow");
        if (addBtn) addBtn.onclick = function () {
          var tb = view.querySelector("#admFormBody");
          tb.insertAdjacentHTML("beforeend", addBtn.dataset.add === "rule" ? ruleRow({}) : sourceRow("", {}));
          wireRowDels();
        };
        wireRowDels();
      }
      Array.prototype.forEach.call(modes.querySelectorAll(".adm-mode"), function (b) {
        b.classList.toggle("on", b.dataset.mode === st.mode);
      });
    }
    function wireRowDels() {
      Array.prototype.forEach.call(view.querySelectorAll(".adm-rowdel"), function (b) {
        b.onclick = function () { var tr = b.closest("tr"); if (tr) tr.remove(); };
      });
    }
    // Pull the current view into st.obj. Throws (raw mode, bad JSON) to the caller.
    function syncFromView() {
      if (st.mode === "raw") {
        var ta = view.querySelector("#admCfgRaw");
        if (ta) st.obj = JSON.parse(ta.value);
      } else {
        st.obj = readForm(st.name, st.obj, view);
      }
    }

    body.querySelector("#admCfgLoad").onclick = async function () {
      msg.textContent = "Loading…";
      try {
        var j = await callFn("admin-config?name=" + sel.value, { method: "GET" });
        st.obj = JSON.parse(j.text);
        st.name = sel.value;
        st.mode = "form";
        modes.style.display = "";
        save.disabled = false;
        render();
        msg.innerHTML = '<span class="adm-muted">loaded ' + esc(j.path) + " (sha " + esc((j.sha || "").slice(0, 7)) + ")</span>";
      } catch (e) { msg.innerHTML = '<span class="fail-txt">✗ ' + esc(e.message) + "</span>"; }
    };

    Array.prototype.forEach.call(modes.querySelectorAll(".adm-mode"), function (b) {
      b.onclick = function () {
        if (b.dataset.mode === st.mode || !st.name) return;
        try { syncFromView(); }
        catch (e) { msg.innerHTML = '<span class="fail-txt">✗ invalid JSON, fix it before switching: ' + esc(e.message) + "</span>"; return; }
        msg.textContent = "";
        st.mode = b.dataset.mode;
        render();
      };
    });

    save.onclick = async function () {
      try { syncFromView(); }
      catch (e) { msg.innerHTML = '<span class="fail-txt">✗ invalid JSON: ' + esc(e.message) + "</span>"; return; }
      var problems = validateConfig(st.name, st.obj);
      if (problems.length) {
        msg.innerHTML = '<div class="fail-txt">✗ Not saved — fix these first:</div>' +
          '<ul class="adm-problems">' + problems.slice(0, 12).map(function (p) {
            return "<li>" + esc(p) + "</li>";
          }).join("") + (problems.length > 12 ? "<li>… and " + (problems.length - 12) + " more</li>" : "") + "</ul>";
        return;
      }
      if (!confirm("Commit this " + st.name + ".json to the private repo?")) return;
      msg.textContent = "Committing…";
      try {
        var j = await callFn("admin-config", { method: "POST", body: { name: st.name, text: JSON.stringify(st.obj, null, 2) } });
        msg.innerHTML = '<span class="ok-txt">✓ committed</span> <a href="' + esc(j.url) +
          '" target="_blank" rel="noopener">' + esc((j.commit || "").slice(0, 7)) + "</a>";
      } catch (e) { msg.innerHTML = '<span class="fail-txt">✗ ' + esc(e.message) + "</span>"; }
    };
  }

  // ── Logs ─────────────────────────────────────────────────────────────────────
  async function renderLogs(body) {
    try {
      var r = await AC.from("pipeline_logs").select("name,kind,captured_at").order("captured_at", { ascending: false }).limit(200);
      if (r.error) throw r.error;
      var seen = {}, names = [];
      (r.data || []).forEach(function (x) { if (!seen[x.name]) { seen[x.name] = 1; names.push(x); } });
      body.innerHTML =
        '<div class="adm-cfg-pick"><label>Log: <select id="admLogSel">' +
        names.map(function (n) { return '<option value="' + esc(n.name) + '">' + esc(n.name) + " · " + esc(n.kind) + "</option>"; }).join("") +
        "</select></label><button id=\"admLogLoad\" class=\"adm-act\">View tail</button></div>" +
        (names.length ? "" : '<div class="adm-empty">No logs shipped yet. Non-OK source logs + health_log.txt are uploaded by push_health.py.</div>') +
        '<pre id="admLogOut" class="adm-log"></pre>';
      body.querySelector("#admLogLoad").onclick = async function () {
        var name = body.querySelector("#admLogSel").value;
        var out = body.querySelector("#admLogOut");
        out.textContent = "loading…";
        var q = await AC.from("pipeline_logs").select("tail,captured_at").eq("name", name).order("captured_at", { ascending: false }).limit(1);
        out.textContent = (q.data && q.data[0] && q.data[0].tail) || "(empty)";
      };
    } catch (e) { err(body, e); }
  }

  // ── Users ────────────────────────────────────────────────────────────────────
  async function renderUsers(body) {
    body.innerHTML = '<h4 class="adm-h">Users</h4><div id="admUsers">loading…</div>';
    var host = body.querySelector("#admUsers");
    try {
      var j = await callFn("admin-users", { method: "GET" });
      host.innerHTML = '<div class="adm-tablewrap"><table class="adm-table"><thead><tr>' +
        "<th>Name</th><th>Email</th><th>Created</th><th>Last sign-in</th><th></th></tr></thead><tbody>" +
        (j.users || []).map(function (u) {
          return "<tr><td>" + esc(u.name || "—") + "</td><td>" + esc(u.email) +
            "</td><td>" + esc((u.created_at || "").slice(0, 10)) +
            "</td><td>" + esc((u.last_sign_in_at || "").slice(0, 10)) + "</td>" +
            '<td><button class="adm-del" data-id="' + esc(u.id) + '" data-email="' + esc(u.email) + '">delete</button></td></tr>';
        }).join("") + "</tbody></table></div>";
      Array.prototype.forEach.call(host.querySelectorAll(".adm-del"), function (b) {
        b.onclick = async function () {
          if (!confirm("Delete user " + b.dataset.email + "? This removes their account and synced data. Cannot be undone.")) return;
          b.disabled = true; b.textContent = "…";
          try { await callFn("admin-users", { method: "POST", body: { id: b.dataset.id } }); b.closest("tr").remove(); }
          catch (e) { alert("Delete failed: " + e.message); b.disabled = false; b.textContent = "delete"; }
        };
      });
    } catch (e) { err(host, e); }
  }
  // ── styles ───────────────────────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById("admStyle")) return;
    var s = document.createElement("style");
    s.id = "admStyle";
    s.textContent =
      "#adminRoot{display:none}" +
      ".adm-overlay{position:fixed;inset:0;background:rgba(10,8,4,.6);z-index:9999;display:flex;align-items:flex-start;justify-content:center;padding:24px;overflow:auto;font-family:'JetBrains Mono',monospace}" +
      ".adm-panel{background:#14110b;color:#e7ddc7;border:1px solid #3a3222;border-radius:8px;width:min(1000px,96vw);box-shadow:0 20px 60px rgba(0,0,0,.5)}" +
      ".adm-head{display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid #3a3222}" +
      ".adm-title{font-size:13px;letter-spacing:.15em;text-transform:uppercase;color:#e8b25a}" +
      ".adm-sub{font-size:10px;color:#8a8069;letter-spacing:.1em}.adm-x{margin-left:auto;background:none;border:1px solid #3a3222;color:#c9c0a8;width:26px;height:26px;border-radius:4px;cursor:pointer}" +
      ".adm-tabs{display:flex;gap:4px;padding:10px 14px 0;flex-wrap:wrap}" +
      ".adm-tab{background:none;border:1px solid #3a3222;color:#b8ad90;padding:6px 12px;font:inherit;font-size:11px;border-radius:4px 4px 0 0;cursor:pointer}" +
      ".adm-tab.on{background:#1f1b12;border-bottom-color:#1f1b12;color:#e8b25a}" +
      ".adm-body{padding:16px 18px;min-height:200px}" +
      ".adm-loading,.adm-muted,.adm-empty,.adm-note,.adm-when{color:#8a8069;font-size:11px}" +
      ".adm-note{margin:6px 0 10px}.adm-when{margin-bottom:10px}" +
      ".adm-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}" +
      ".adm-card{border:1px solid #3a3222;border-radius:6px;padding:10px 12px;background:#191510}" +
      ".adm-card.ok{border-left:3px solid #4a7c46}.adm-card.warn{border-left:3px solid #b98a1e}.adm-card.fail{border-left:3px solid #a33}" +
      ".adm-card-l{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#8a8069}" +
      ".adm-card-b{font-size:18px;margin:4px 0;color:#efe6cf}.adm-card-s{font-size:10px;color:#8a8069}" +
      ".adm-card-fix{font-size:10px;color:#e0b452;margin-top:6px;line-height:1.35}" +
      ".adm-overview-head{display:flex;align-items:center;gap:8px;margin-bottom:10px}.adm-overview-head .adm-when{margin-bottom:0}" +
      ".adm-h{margin:18px 0 8px;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#c9a24a}" +
      ".adm-runs{display:flex;flex-direction:column;gap:4px}.adm-run{display:flex;align-items:center;gap:8px;font-size:11px}" +
      ".adm-run a{color:#cdb98a;text-decoration:none}.adm-run-t{margin-left:auto;color:#6f6754}" +
      ".pill{font-size:9px;padding:2px 6px;border-radius:3px;text-transform:uppercase;letter-spacing:.08em}" +
      ".pill.ok{background:#20331e;color:#7fbf76}.pill.warn{background:#33290f;color:#e0b452}.pill.fail{background:#3a1616;color:#e78585}" +
      ".adm-filters{display:flex;justify-content:space-between;align-items:center;font-size:11px;margin-bottom:8px}" +
      ".adm-tablewrap{overflow-x:auto}.adm-table{width:100%;border-collapse:collapse;font-size:11px}" +
      ".adm-table th{text-align:left;color:#8a8069;font-weight:400;border-bottom:1px solid #3a3222;padding:5px 8px}" +
      ".adm-table td{padding:5px 8px;border-bottom:1px solid #241f16}.adm-table .pos{color:#7fbf76}.adm-table .neg{color:#e78585}" +
      ".adm-btns{display:flex;flex-wrap:wrap;gap:8px}.adm-act{background:#1f1b12;border:1px solid #c97f0c;color:#e8b25a;padding:7px 12px;font:inherit;font-size:11px;border-radius:4px;cursor:pointer}" +
      ".adm-act.loc{border-color:#4a5a7c;color:#8fb0e0}.adm-act:disabled{opacity:.5;cursor:default}" +
      ".adm-msg{font-size:11px;margin-top:8px;min-height:16px}.ok-txt{color:#7fbf76}.fail-txt{color:#e78585}" +
      ".adm-cfg-pick{display:flex;gap:8px;align-items:center;margin-bottom:8px;font-size:11px;flex-wrap:wrap}" +
      ".adm-cfg-pick select{background:#191510;color:#e7ddc7;border:1px solid #3a3222;padding:5px;font:inherit}" +
      ".adm-textarea{width:100%;height:320px;background:#0e0c08;color:#d7ceb6;border:1px solid #3a3222;border-radius:4px;padding:10px;font:inherit;font-size:11px;box-sizing:border-box}" +
      ".adm-modes{display:inline-flex;gap:0;margin:0 4px}.adm-mode{background:#191510;border:1px solid #3a3222;color:#b8ad90;padding:6px 10px;font:inherit;font-size:11px;cursor:pointer}" +
      ".adm-mode:first-child{border-radius:4px 0 0 4px}.adm-mode:last-child{border-radius:0 4px 4px 0;border-left:none}.adm-mode.on{background:#1f1b12;color:#e8b25a;border-color:#c97f0c}" +
      ".adm-cfg-view{margin-bottom:8px}.adm-formhint{font-size:11px;color:#8a8069;margin-bottom:8px}.adm-formhint b{color:#c9a24a;font-weight:400}" +
      ".adm-form td{vertical-align:top}.adm-in{width:100%;background:#0e0c08;color:#d7ceb6;border:1px solid #3a3222;border-radius:3px;padding:4px 6px;font:inherit;font-size:11px;box-sizing:border-box}" +
      ".adm-in.narrow{min-width:70px}.adm-in.wide{min-width:180px}select.adm-in{cursor:pointer}" +
      ".adm-addrow{margin-top:8px}.adm-rowdel{width:22px;text-align:center;padding:3px 0}" +
      ".adm-log{background:#0e0c08;color:#c7bfa6;border:1px solid #3a3222;border-radius:4px;padding:10px;font-size:10px;max-height:420px;overflow:auto;white-space:pre-wrap}" +
      ".adm-queue-head{display:flex;align-items:center;gap:8px}" +
      ".adm-refresh{background:none;border:1px solid #3a3222;color:#c9c0a8;width:24px;height:24px;border-radius:4px;cursor:pointer;font-size:12px;line-height:1}" +
      ".adm-agent{font-size:11px;margin:8px 0;padding:7px 10px;border-radius:4px;border:1px solid #3a3222}" +
      ".adm-agent.ok{background:#16210f;border-color:#2f4a26;color:#8fc47f}" +
      ".adm-agent.warn{background:#241d0c;border-color:#4a3c14;color:#e0b452}" +
      ".adm-agent.fail{background:#25100f;border-color:#5a2a2a;color:#e79a9a}" +
      ".adm-agent code{color:inherit;background:rgba(0,0,0,.25);padding:0 3px;border-radius:2px}" +
      ".adm-qres{color:#8a8069;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
      ".adm-problems{margin:6px 0 0;padding-left:18px;font-size:11px;color:#e79a9a}.adm-problems li{margin:2px 0}" +
      ".adm-flags{margin-bottom:12px}.adm-flag{display:inline-flex;gap:5px;align-items:center;margin:0 12px 6px 0;font-size:11px}" +
      ".adm-del{background:#2a1414;border:1px solid #5a2a2a;color:#e79a9a;padding:3px 8px;font:inherit;font-size:10px;border-radius:3px;cursor:pointer}" +
      ".adm-err{color:#e78585;font-size:12px}.adm-hint{color:#8a8069;font-size:10px;margin-top:6px}";
    document.head.appendChild(s);
  }
})();
