/**
 * Query parsing and full-text match with synonym expansion.
 * 1) Phrase + synonym needles (OR within concept)
 * 2) Multi-token: each token must match any needle from its synonym group
 */
(function (global) {
  const { normalizeSearchText, compactSearchText } = global.SearchNormalize;
  const Syn = global.SearchSynonyms;

  const MIN_TOKEN_LEN = Syn ? Syn.MIN_TOKEN_LEN : 4;

  function parseQuery(q) {
    return normalizeSearchText(q).split(' ').filter(Boolean);
  }

  function matchNeedles(job, needles) {
    if (!needles.length) return false;
    if (Syn) return Syn.hayMatchesAny(job, needles);
    const hay = job._searchCompact || '';
    return needles.some(function (n) {
      return n.length > 0 && hay.includes(n);
    });
  }

  function phraseNeedles(raw) {
    const normalized = normalizeSearchText(raw);
    const needles = new Set();

    const phrase = compactSearchText(normalized);
    if (phrase.length > 0) needles.add(phrase);

    if (Syn) {
      Syn.needlesForPhrase(normalized).forEach(function (n) {
        needles.add(n);
      });
    }

    return [...needles];
  }

  function tokenNeedles(token) {
    if (Syn) return Syn.needlesForToken(token);
    const c = compactSearchText(token);
    return c.length >= 2 ? [c] : [];
  }

  function matchesSearch(job, q) {
    const raw = String(q || '').trim();
    if (!raw) return true;

    const hay = job._searchCompact || '';
    if (!hay) return false;

    if (matchNeedles(job, phraseNeedles(raw))) {
      return true;
    }

    const tokens = parseQuery(raw);
    if (tokens.length <= 1) return false;

    return tokens.every(function (token) {
      const needles = tokenNeedles(token);
      const longEnough = needles.filter(function (n) {
        return n.length >= MIN_TOKEN_LEN;
      });
      if (longEnough.length) return matchNeedles(job, longEnough);
      return matchNeedles(job, needles);
    });
  }

  function collectNeedles(raw) {
    const needles = new Set();
    phraseNeedles(raw).forEach(function (n) {
      needles.add(n);
    });
    parseQuery(raw).forEach(function (token) {
      tokenNeedles(token).forEach(function (n) {
        needles.add(n);
      });
    });
    return [...needles];
  }

  global.SearchQuery = {
    parseQuery,
    matchesSearch,
    phraseNeedles,
    tokenNeedles,
    collectNeedles,
    MIN_TOKEN_LEN,
  };
})(typeof window !== 'undefined' ? window : global);
