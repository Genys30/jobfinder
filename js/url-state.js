/**
 * Sync filter state with URL query string (?q=frontend&city=Tel+Aviv).
 */
(function (global) {
  const FORM_KEYS = ['q', 'company', 'segment', 'level', 'date', 'sector', 'source', 'worktype', 'sort'];

  let hooks = {
    getElement: function (id) {
      return document.getElementById(id);
    },
    getSelectedCities: function () {
      return new Set();
    },
    setSelectedCities: function () {},
  };

  function init(customHooks) {
    if (customHooks) Object.assign(hooks, customHooks);
  }

  function readFromUrl() {
    const sp = new URLSearchParams(location.search);
    if (![...sp.keys()].length) return false;

    FORM_KEYS.forEach(function (key) {
      const el = hooks.getElement(key);
      if (!el) return;
      if (sp.has(key)) el.value = sp.get(key);
    });

    const cities = sp.get('cities');
    if (cities) {
      hooks.setSelectedCities(
        cities.split(',').map(function (c) {
          return decodeURIComponent(c.trim());
        }).filter(Boolean)
      );
    }

    return true;
  }

  function replaceFromCriteria(criteria) {
    const sp = new URLSearchParams();

    FORM_KEYS.forEach(function (key) {
      const val = criteria[key];
      if (val) sp.set(key, val);
    });

    if (criteria.selectedCities && criteria.selectedCities.size) {
      sp.set(
        'cities',
        [...criteria.selectedCities].map(encodeURIComponent).join(',')
      );
    }

    const qs = sp.toString();
    const url = qs ? location.pathname + '?' + qs : location.pathname;
    history.replaceState(null, '', url);
  }

  function criteriaFromDom(getters) {
    const g = getters || {};
    return {
      q: (g.q && g.q.value.trim()) || '',
      company: (g.company && g.company.value) || '',
      segment: (g.segment && g.segment.value) || '',
      level: (g.level && g.level.value) || '',
      date: (g.date && g.date.value) || '',
      sector: (g.sector && g.sector.value) || '',
      source: (g.source && g.source.value) || '',
      worktype: (g.worktype && g.worktype.value) || '',
      sort: (g.sort && g.sort.value) || '',
      selectedCities: hooks.getSelectedCities(),
    };
  }

  global.UrlState = {
    init,
    readFromUrl,
    replaceFromCriteria,
    criteriaFromDom,
    FORM_KEYS,
  };
})(typeof window !== 'undefined' ? window : global);
