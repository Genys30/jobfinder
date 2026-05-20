/**
 * Text normalization for job search (Stage 0).
 * Handles front-end / front end / frontend-style variants via compact form.
 */
(function (global) {
  function normalizeSearchText(s) {
    return String(s || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/\p{M}/gu, '')
      .replace(/[-_/.,]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function compactSearchText(s) {
    return normalizeSearchText(s).replace(/\s+/g, '');
  }

  /** Whole words for Set lookup (min length 2). */
  function tokenizeSearchText(s) {
    return normalizeSearchText(s).split(/\s+/).filter(function (t) {
      return t.length >= 2;
    });
  }

  function searchTokenSet(s) {
    return new Set(tokenizeSearchText(s));
  }

  global.SearchNormalize = {
    normalizeSearchText,
    compactSearchText,
    tokenizeSearchText,
    searchTokenSet,
  };
})(typeof window !== 'undefined' ? window : global);
