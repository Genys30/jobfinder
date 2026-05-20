/**
 * Cancellable chunked filter runner — yields between chunks so the main thread can handle input.
 */
(function (global) {
  let currentRunId = 0;

  const DEFAULT_CHUNK_SIZE = 500;
  const DEFAULT_RENDER_LIMIT = 200;

  function yieldToBrowser() {
    return new Promise(function (resolve) {
      if (typeof global.requestIdleCallback === 'function') {
        global.requestIdleCallback(
          function () {
            resolve();
          },
          { timeout: 50 }
        );
      } else {
        setTimeout(resolve, 0);
      }
    });
  }

  function cancel() {
    currentRunId++;
  }

  function getRunId() {
    return currentRunId;
  }

  async function filterChunked(jobs, criteria, helpers, runId, chunkSize, jobPassesFn) {
    const results = [];
    const size = chunkSize || DEFAULT_CHUNK_SIZE;
    const pass = jobPassesFn || (global.JobFilters && global.JobFilters.jobPassesFilters);

    for (let i = 0; i < jobs.length; i += size) {
      if (runId !== currentRunId) return null;

      const end = Math.min(i + size, jobs.length);
      for (let j = i; j < end; j++) {
        if (pass(jobs[j], criteria, helpers)) {
          results.push(jobs[j]);
        }
      }

      await yieldToBrowser();
    }

    if (runId !== currentRunId) return null;
    return results;
  }

  async function run(options) {
    const runId = ++currentRunId;

    const jobs = options.jobs || [];
    const criteria = options.criteria || {};
    const helpers = options.helpers || {};
    const chunkSize = options.chunkSize || DEFAULT_CHUNK_SIZE;
    const renderLimit =
      options.renderLimit != null ? options.renderLimit : DEFAULT_RENDER_LIMIT;

    if (options.onStart) {
      options.onStart(runId);
    }

    if (!jobs.length) {
      if (runId !== currentRunId) return;
      if (options.onDone) {
        options.onDone({
          runId: runId,
          results: [],
          total: 0,
          initialVisible: 0,
          renderLimit: renderLimit,
        });
      }
      return;
    }

    if (global.JobStore && typeof global.JobStore.enrichJobs === 'function') {
      global.JobStore.enrichJobs(jobs);
    }

    const results = await filterChunked(
      jobs,
      criteria,
      helpers,
      runId,
      chunkSize,
      options.jobPassesFilters
    );

    if (runId !== currentRunId || results === null) {
      if (options.onStale) options.onStale(runId);
      return;
    }

    if (helpers.parseDate && global.SearchRank && typeof global.SearchRank.applyResultSort === 'function') {
      global.SearchRank.applyResultSort(results, {
        q: criteria.q,
        sort: criteria.sort || 'date',
        parseDate: helpers.parseDate,
      });
    }

    if (runId !== currentRunId) {
      if (options.onStale) options.onStale(runId);
      return;
    }

    const initialVisible = Math.min(renderLimit, results.length);

    if (options.onDone) {
      options.onDone({
        runId: runId,
        results: results,
        total: results.length,
        initialVisible: initialVisible,
        renderLimit: renderLimit,
      });
    }
  }

  global.SearchRunner = {
    run: run,
    cancel: cancel,
    getRunId: getRunId,
  };
})(typeof window !== 'undefined' ? window : globalThis);
