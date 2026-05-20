/**
 * Relevance scoring after text match — title weighted highest, then company, etc.
 */
(function (global) {
  const { normalizeSearchText, compactSearchText } = global.SearchNormalize;
  const Query = global.SearchQuery;
  const Syn = global.SearchSynonyms;

  const FIELD_WEIGHTS = {
    title: 100,
    company: 40,
    category: 25,
    fnArea: 20,
    city: 15,
    requirements: 10,
    description: 5,
  };

  const BONUS_ALL_TOKENS_IN_TITLE = 50;
  const BONUS_PHRASE_IN_TITLE = 80;
  const BONUS_TITLE_STARTS = 30;

  function fieldMatches(field, needle) {
    if (Syn) return Syn.needleMatchesField(field, needle);
    if (!field || !needle) return false;
    return field.compact.includes(needle);
  }

  function tokenMatchesField(field, token) {
    if (!field || !token) return false;
    const needles = Query ? Query.tokenNeedles(token) : [compactSearchText(token)];
    for (let i = 0; i < needles.length; i++) {
      if (fieldMatches(field, needles[i])) return true;
    }
    return false;
  }

  function score(job, rawQuery) {
    const raw = String(rawQuery || '').trim();
    if (!raw) return 0;

    if (!job._searchEnriched && global.JobStore) {
      global.JobStore.enrichJob(job);
    }

    const fields = job._fieldSearch || {};
    const needles = Query && Query.collectNeedles ? Query.collectNeedles(raw) : [];
    const tokens = Query ? Query.parseQuery(raw) : normalizeSearchText(raw).split(/\s+/);
    const phraseCompact = compactSearchText(raw);
    let score = 0;

    Object.keys(FIELD_WEIGHTS).forEach(function (key) {
      const fd = fields[key];
      const weight = FIELD_WEIGHTS[key];
      if (!fd || !weight) return;
      for (let i = 0; i < needles.length; i++) {
        if (fieldMatches(fd, needles[i])) {
          score += weight;
          return;
        }
      }
    });

    const titleField = fields.title;
    if (titleField && tokens.length > 0) {
      const allInTitle = tokens.every(function (t) {
        return tokenMatchesField(titleField, t);
      });
      if (allInTitle) score += BONUS_ALL_TOKENS_IN_TITLE;
    }

    if (titleField && phraseCompact.length >= 4 && titleField.compact.includes(phraseCompact)) {
      score += BONUS_PHRASE_IN_TITLE;
    }

    if (titleField && titleField.norm) {
      const normQ = normalizeSearchText(raw);
      if (normQ && titleField.norm.indexOf(normQ) === 0) {
        score += BONUS_TITLE_STARTS;
      }
    }

    return score;
  }

  /** Sort by relevance desc, then date desc (parseDate from caller). */
  function compareJobs(a, b, rawQuery, parseDate) {
    const q = String(rawQuery || '').trim();
    if (q) {
      const sa = a._searchScore != null ? a._searchScore : score(a, q);
      const sb = b._searchScore != null ? b._searchScore : score(b, q);
      if (sa !== sb) return sb - sa;
    }

    const da = parseDate ? parseDate(a.updated) : null;
    const db = parseDate ? parseDate(b.updated) : null;
    if (!da && !db) return 0;
    if (!da) return 1;
    if (!db) return -1;
    return db - da;
  }

  function rankJobs(jobs, rawQuery, parseDate) {
    const q = String(rawQuery || '').trim();
    if (!q || !jobs.length) return jobs;

    for (let i = 0; i < jobs.length; i++) {
      jobs[i]._searchScore = score(jobs[i], q);
    }

    jobs.sort(function (a, b) {
      return compareJobs(a, b, q, parseDate);
    });
    return jobs;
  }

  /** Newest first — same tie-break rules as elsewhere. */
  function sortByDateDesc(jobs, parseDateFn) {
    if (!jobs || !jobs.length || !parseDateFn) return jobs;
    jobs.sort(function (a, b) {
      const da = parseDateFn(a.updated);
      const db = parseDateFn(b.updated);
      if (!da && !db) return 0;
      if (!da) return 1;
      if (!db) return -1;
      return db - da;
    });
    return jobs;
  }

  /**
   * After filter: either relevance (score + date tie-break) or pure date.
   * Without text query, date sort is always used.
   */
  function applyResultSort(jobs, opts) {
    const q = String((opts && opts.q) || '').trim();
    const sort = (opts && opts.sort) || 'date';
    const parseDateFn = opts && opts.parseDate;
    if (!jobs || !jobs.length) return jobs;

    if (!q || sort === 'date') {
      return sortByDateDesc(jobs, parseDateFn);
    }
    return rankJobs(jobs, q, parseDateFn);
  }

  global.SearchRank = {
    score,
    rankJobs,
    compareJobs,
    FIELD_WEIGHTS,
    sortByDateDesc,
    applyResultSort,
  };
})(typeof window !== 'undefined' ? window : global);
