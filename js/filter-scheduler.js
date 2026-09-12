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
      const fire = function () {
        rafId = null;
        const run = pendingFn;
        pendingFn = null;
        if (run) run();
      };
      // rAF never fires in a hidden tab — loaders finishing in a background
      // tab would leave the page stuck on the loading state until focused.
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        fire();
      } else {
        rafId = requestAnimationFrame(fire);
      }
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
