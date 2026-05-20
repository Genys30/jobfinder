/**
 * Debounce heavy filter+render passes (search typing).
 */
(function (global) {
  const DEBOUNCE_MS = 420;
  let timer = null;
  let rafId = null;
  let pendingFn = null;

  function cancel() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  function schedule(fn) {
    pendingFn = fn;
    cancel();
    timer = setTimeout(function () {
      timer = null;
      rafId = requestAnimationFrame(function () {
        rafId = null;
        const run = pendingFn;
        pendingFn = null;
        if (run) run();
      });
    }, DEBOUNCE_MS);
  }

  function flush(fn) {
    cancel();
    pendingFn = null;
    if (fn) fn();
  }

  global.FilterScheduler = {
    DEBOUNCE_MS,
    schedule,
    flush,
    cancel,
  };
})(typeof window !== 'undefined' ? window : global);
