/**
 * Structured filters + text search orchestration.
 */
(function (global) {
  function jobPassesFilters(job, criteria, helpers) {
    const h = helpers || {};

    if (criteria.selectedCities && criteria.selectedCities.size) {
      const city = h.normalizeCity ? h.normalizeCity(job.city) : job.city;
      if (!criteria.selectedCities.has(city)) return false;
    }

    if (criteria.company && job.company !== criteria.company) return false;

    if (criteria.segFilter && h.classifySegment) {
      if (h.classifySegment(job.title) !== criteria.segFilter) return false;
    }

    if (criteria.lvlFilter && h.classifyLevel) {
      if (h.classifyLevel(job.title) !== criteria.lvlFilter) return false;
    }

    if (criteria.secFilter && h.classifyEmployerType) {
      if (h.classifyEmployerType(job.company, job.title, job.source) !== criteria.secFilter) {
        return false;
      }
    }

    if (criteria.srcFilter && job.source !== criteria.srcFilter) return false;

    if (criteria.wtFilter) {
      const wt = job.workType || '';
      if (wt !== criteria.wtFilter && !(criteria.wtFilter === 'remote' && job.city === 'מהבית')) {
        return false;
      }
    }

    if (criteria.ptFilter) {
      const pt = (job.positionType || '').toLowerCase().replace(/-/g, '_');
      if (criteria.ptFilter === 'full_time') {
        if (pt && pt !== 'full_time') return false;
      } else {
        if (pt !== criteria.ptFilter) return false;
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
