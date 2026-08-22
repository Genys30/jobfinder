/**
 * Sync filter state with URL query string.
 * Multi-select filters (segment, level, sector, source, worktype, positiontype)
 * are stored as comma-separated values: ?segment=rd,data&level=senior
 */
(function (global) {
  // Keys that map to plain <select> or <input> DOM elements
  const PLAIN_KEYS = ['q', 'company', 'date', 'sort', 'entropy'];
  // Keys that map to multi-select Sets — values are comma-separated in URL
  const MS_KEYS = ['segment', 'level', 'sector', 'source', 'worktype', 'positiontype'];

  let hooks = {
    getElement: function (id) { return document.getElementById(id); },
    getSelectedCities: function () { return new Set(); },
    setSelectedCities: function () {},
    // Multi-select hooks — set by index.html init()
    getMs: function (key) { return new Set(); },
    setMs: function (key, vals) {},
  };

  function init(customHooks) {
    if (customHooks) Object.assign(hooks, customHooks);
  }

  function readFromUrl() {
    const sp = new URLSearchParams(location.search);
    if (![...sp.keys()].length) return false;

    // Plain single-value fields
    PLAIN_KEYS.forEach(function (key) {
      const el = hooks.getElement(key);
      if (el && sp.has(key)) el.value = sp.get(key);
    });

    // Multi-select fields
    MS_KEYS.forEach(function (key) {
      if (sp.has(key)) {
        const vals = sp.get(key).split(',').map(v => decodeURIComponent(v.trim())).filter(Boolean);
        if (vals.length) hooks.setMs(key, vals);
      }
    });

    // Cities
    const cities = sp.get('cities');
    if (cities) {
      hooks.setSelectedCities(
        cities.split(',').map(function (c) { return decodeURIComponent(c.trim()); }).filter(Boolean)
      );
    }

    return true;
  }

  function replaceFromCriteria(criteria) {
    const sp = new URLSearchParams();

    PLAIN_KEYS.forEach(function (key) {
      const val = criteria[key];
      if (val && !(key === 'sort' && val === 'date')) sp.set(key, val);
    });

    // Multi-select: criteria[key] is already serialized as comma-joined string
    MS_KEYS.forEach(function (key) {
      const val = criteria[key];
      if (val && val.length) sp.set(key, val);
    });

    if (criteria.selectedCities && criteria.selectedCities.size) {
      sp.set('cities', [...criteria.selectedCities].map(encodeURIComponent).join(','));
    }

    const qs = sp.toString();
    const url = qs ? location.pathname + '?' + qs : location.pathname;
    history.replaceState(null, '', url);
  }

  global.UrlState = {
    init,
    readFromUrl,
    replaceFromCriteria,
    PLAIN_KEYS,
    MS_KEYS,
  };
})(typeof window !== 'undefined' ? window : global);
