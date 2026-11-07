/**
 * Debounce heavy filter+render passes (search typing).
 */
(function (global) {
  const DEBOUNCE_MS = 420;
  // rAF can also stall while visibilityState still says 'visible' (an occluded
  // window, an embedded preview pane) — measured 2026-11-03: no frame in 3 s and the
  // list stayed on its skeleton. Backstop: fire anyway after this long.
  const RAF_BACKSTOP_MS = 500;
  let timer = null;
  let rafId = null;
  let backstop = null;
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
    if (backstop) {
      clearTimeout(backstop);
      backstop = null;
    }
  }

  function schedule(fn) {
    pendingFn = fn;
    cancel();
    timer = setTimeout(function () {
      timer = null;
      const fire = function () {
        if (rafId) cancelAnimationFrame(rafId);
        if (backstop) clearTimeout(backstop);
        rafId = null;
        backstop = null;
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
        backstop = setTimeout(fire, RAF_BACKSTOP_MS);
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
