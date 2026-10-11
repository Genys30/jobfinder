/**
 * Structured filters + text search orchestration.
 * segFilter, lvlFilter, secFilter, srcFilter, wtFilter, ptFilter
 * are now Sets (multi-select). Empty Set = no filter on that dimension.
 */
(function (global) {
  function _setActive(val) {
    return val && val.size && val.size > 0;
  }

  function jobPassesFilters(job, criteria, helpers) {
    const h = helpers || {};

    if (criteria.selectedCities && criteria.selectedCities.size) {
      const city = h.normalizeCity ? h.normalizeCity(job.city) : job.city;
      if (!criteria.selectedCities.has(city)) return false;
    }

    if (criteria.company && job.company !== criteria.company) return false;

    // Recently-funded: only roles at an employer with a resolved round <=12mo old
    // (helpers.fundedRecent resolves the employer via the identity graph + _FUND).
    if (criteria.fundedOnly && h.fundedRecent && !h.fundedRecent(job)) return false;

    // segFilter — Set of segment values (e.g. Set{'rd','data'})
    if (_setActive(criteria.segFilter) && h.classifySegment) {
      if (!criteria.segFilter.has(h.classifySegment(job.title))) return false;
    }

    // lvlFilter — Set of level values
    if (_setActive(criteria.lvlFilter) && h.classifyLevel) {
      if (!criteria.lvlFilter.has(h.classifyLevel(job.title))) return false;
    }

    // secFilter — Set of employer type values
    if (_setActive(criteria.secFilter) && h.classifyEmployerType) {
      if (!criteria.secFilter.has(h.classifyEmployerType(job.company, job.title, job.source))) {
        return false;
      }
    }

    // srcFilter — Set of source values.
    // Meitar is a law firm scraped via Comeet (source='comeet'), so it must also
    // match the 'lawfirms' source group — see LAWFIRM_COMEET check in index.html.
    if (_setActive(criteria.srcFilter)) {
      const lawfirmComeet = job.source === 'comeet' && job.company === 'Meitar';
      if (!criteria.srcFilter.has(job.source) &&
          !(lawfirmComeet && criteria.srcFilter.has('lawfirms'))) return false;
    }

    // wtFilter — Set of work type values
    if (_setActive(criteria.wtFilter)) {
      const wt = job.workType || '';
      const matchRemote = criteria.wtFilter.has('remote') && job.city === 'מהבית';
      if (!criteria.wtFilter.has(wt) && !matchRemote) return false;
    }

    // ptFilter — Set of position type values
    if (_setActive(criteria.ptFilter)) {
      const pt = (job.positionType || '').toLowerCase().replace(/-/g, '_');
      // full_time is the default — if full_time selected, also include blank positionType
      if (criteria.ptFilter.has('full_time') && criteria.ptFilter.size === 1) {
        if (pt && pt !== 'full_time') return false;
      } else if (criteria.ptFilter.has('full_time')) {
        // multiple selected including full_time: include blank positionType too
        if (pt && !criteria.ptFilter.has(pt)) return false;
      } else {
        if (!criteria.ptFilter.has(pt)) return false;
      }
    }

    if (criteria.q && global.SearchQuery && !global.SearchQuery.matchesSearch(job, criteria.q)) {
      return false;
    }

    if (criteria.cutoff != null && h.parseDate) {
      // One rule for every source: dated rows must meet the cutoff, undated
      // rows pass (the old techmap-only exclusion was asymmetric — audit M12;
      // techmap is removed from the frontend anyway).
      const d = h.parseDate(job.updated);
      if (d && d.getTime() < criteria.cutoff) return false;
    }

    return true;
  }

  global.JobFilters = {
    jobPassesFilters,
  };
})(typeof window !== 'undefined' ? window : global);
