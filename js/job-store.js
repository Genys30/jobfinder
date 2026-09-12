/**
 * Job enrichment: search blob + normalized index fields (client-side only).
 */
(function (global) {
  const { normalizeSearchText, compactSearchText, tokenizeSearchText, searchTokenSet } =
    global.SearchNormalize;

  function buildSearchBlob(job) {
    const parts = [
      job.title,
      job.company,
      job.city,
      job.category,
      job.description,
      job.requirements,
    ];
    if (job.source === 'techmap' && job.fnArea) {
      parts.push(job.fnArea);
    }
    return parts.filter(Boolean).join(' ');
  }

  const RANK_FIELDS = ['title', 'company', 'city', 'category', 'description', 'requirements'];

  function fieldSearchIndex(value) {
    if (value == null || value === '') return null;
    const text = String(value);
    return {
      norm: normalizeSearchText(text),
      compact: compactSearchText(text),
      tokens: searchTokenSet(text),
    };
  }

  function enrichJob(job) {
    if (!job || job._searchEnriched) return job;
    const blob = buildSearchBlob(job);
    job._searchNorm = normalizeSearchText(blob);
    job._searchCompact = compactSearchText(blob);
    job._searchTokens = tokenizeSearchText(blob);
    job._searchTokenSet = searchTokenSet(blob);

    job._fieldSearch = {};
    for (let i = 0; i < RANK_FIELDS.length; i++) {
      const key = RANK_FIELDS[i];
      const idx = fieldSearchIndex(job[key]);
      if (idx) job._fieldSearch[key] = idx;
    }
    if (job.source === 'techmap' && job.fnArea) {
      const idx = fieldSearchIndex(job.fnArea);
      if (idx) job._fieldSearch.fnArea = idx;
    }

    job._searchEnriched = true;
    return job;
  }

  function enrichJobs(jobs) {
    if (!jobs || !jobs.length) return jobs;
    for (let i = 0; i < jobs.length; i++) {
      enrichJob(jobs[i]);
    }
    return jobs;
  }

  global.JobStore = {
    buildSearchBlob,
    enrichJob,
    enrichJobs,
  };
})(typeof window !== 'undefined' ? window : global);
