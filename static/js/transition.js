// ============================================
// VANILLA COFFEE — PAGE TRANSITION LOADER
// 1 second smooth animation between pages
// ============================================
(function () {
  const STORAGE_KEY = 'vc:transitioning';
  const HOLD_MS = 500;
  const FADE_OUT_MS = 250;

  let overlay = document.getElementById('pageTransition');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.className = 'page-transition';
    overlay.id = 'pageTransition';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML = [
      '<div class="page-transition-cup">',
      '  <div class="page-transition-steam"><span></span><span></span><span></span></div>',
      '  <div class="page-transition-cup-body"></div>',
      '  <div class="page-transition-cup-handle"></div>',
      '</div>',
      '<div class="page-transition-text">Vanilla<span>COFFEE</span></div>',
      '<div class="page-transition-bar"><i></i></div>',
    ].join('');
    document.body.appendChild(overlay);
  }

  function showOverlay() {
    overlay.classList.add('show');
    overlay.setAttribute('aria-hidden', 'false');
  }
  function hideOverlay() {
    overlay.classList.remove('show');
    overlay.setAttribute('aria-hidden', 'true');
  }

  // If we arrived from an internal navigation, fade overlay out smoothly.
  if (sessionStorage.getItem(STORAGE_KEY) === '1') {
    showOverlay();
    sessionStorage.removeItem(STORAGE_KEY);
    // Wait one paint, then hide
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setTimeout(hideOverlay, FADE_OUT_MS);
      });
    });
  }

  function shouldIntercept(a, url) {
    if (!a || !url) return false;
    if (a.target && a.target !== '' && a.target !== '_self') return false;
    if (a.hasAttribute('download')) return false;
    if (a.dataset.noTransition === '1') return false;
    if (a.closest('[data-no-transition="1"]')) return false;
    if (url.origin !== window.location.origin) return false;
    // Pure same-page hash — let browser handle smooth scrolling
    if (url.pathname === window.location.pathname &&
        url.search === window.location.search &&
        url.hash) return false;
    return true;
  }

  document.addEventListener('click', (e) => {
    if (e.defaultPrevented) return;
    if (e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    const a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    const href = a.getAttribute('href');
    if (!href || href.startsWith('javascript:')) return;
    if (href.startsWith('#')) return;
    if (href.startsWith('mailto:') || href.startsWith('tel:')) return;

    let url;
    try { url = new URL(href, window.location.href); } catch (_e) { return; }
    if (!shouldIntercept(a, url)) return;

    e.preventDefault();
    showOverlay();
    sessionStorage.setItem(STORAGE_KEY, '1');
    setTimeout(() => { window.location.href = url.href; }, HOLD_MS);
  }, true);

  // Same trick for full-form submissions (admin CRUD)
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!form || form.dataset.noTransition === '1') return;
    if (form.target && form.target !== '' && form.target !== '_self') return;
    // Skip GET search forms within the same page (no full nav)
    const method = (form.getAttribute('method') || 'get').toLowerCase();
    const action = form.getAttribute('action') || window.location.href;
    let url;
    try { url = new URL(action, window.location.href); } catch (_e) { return; }
    if (url.origin !== window.location.origin) return;
    // For GET forms to same path with no fields, skip
    if (method === 'get' && url.pathname === window.location.pathname && !form.querySelector('input,select,textarea')) {
      return;
    }
    showOverlay();
    sessionStorage.setItem(STORAGE_KEY, '1');
  }, true);

  // On back/forward bfcache restore — hide overlay
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) {
      sessionStorage.removeItem(STORAGE_KEY);
      hideOverlay();
    }
  });

  // Safety: hide overlay if page is hidden (user opened a new tab etc.)
  window.addEventListener('beforeunload', () => {
    // keep overlay shown — page is about to navigate
  });
})();
