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

    // srcFilter — Set of source values
    if (_setActive(criteria.srcFilter)) {
      if (!criteria.srcFilter.has(job.source)) return false;
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
      const d = h.parseDate(job.updated);
      if (job.source === 'techmap' && (!d || d.getTime() < criteria.cutoff)) return false;
      if (job.source !== 'techmap' && d && d.getTime() < criteria.cutoff) return false;
    }

    return true;
  }

  global.JobFilters = {
    jobPassesFilters,
  };
})(typeof window !== 'undefined' ? window : global);
