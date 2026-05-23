// ============================================
// VANILLA COFFEE — APP LOGIC (bilingual)
// ============================================

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

function parseJsonScript(id, fallback) {
  const el = document.getElementById(id);
  if (!el) return fallback;
  try {
    return JSON.parse(el.textContent);
  } catch (_err) {
    return fallback;
  }
}

// ---------- State ----------
const body = document.body;
const state = {
  lang:  body.dataset.lang  || 'ru',
  table: body.dataset.table || '',
  cat: body.dataset.cat || 'all',
  search: '',
  cart: JSON.parse(localStorage.getItem('vanilla_cart') || '[]'),
  categories: [],
  products: [],
  i18n: {},        // {key: {ru,uz}}
  current: null,   // product opened in detail modal
  currentSize: null,
};

function saveCart() { localStorage.setItem('vanilla_cart', JSON.stringify(state.cart)); }

// ---------- i18n helpers ----------
function t(key, vars = {}) {
  const entry = state.i18n[key];
  let s = (entry && (entry[state.lang] || entry.ru)) || key;
  for (const k in vars) s = s.replace('{' + k + '}', vars[k]);
  return s;
}
const fmt = (n) => n.toLocaleString('ru-RU') + ' ' + t('curr.sum');
const sizeLabel = (s) => s.kind === 'piece' ? s.label : s.label + ' ' + t('curr.ml');
const productName = (p) => (p.name && p.name[state.lang]) || p.name.ru;
const productDesc = (p) => (p.desc && p.desc[state.lang]) || p.desc.ru;
const productIng  = (p) => (p.ingredients && p.ingredients[state.lang]) || p.ingredients.ru || [];
const productTag  = (p) => p.tag && (p.tag[state.lang] || p.tag.ru) || '';
const catName     = (c) => (c.name && c.name[state.lang]) || c.name.ru;

// ---------- DOM translation pass ----------
function applyI18n() {
  $$('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    el.textContent = t(key);
  });
  $$('[data-i18n-html]').forEach((el) => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  $$('[data-i18n-attr]').forEach((el) => {
    const [attr, key] = el.dataset.i18nAttr.split('|');
    el.setAttribute(attr, t(key));
  });
  document.documentElement.lang = state.lang;
  // language switcher chip
  const flagEl = $('#langFlag'), codeEl = $('#langCode');
  if (flagEl) flagEl.textContent = state.lang === 'ru' ? '🇷🇺' : '🇺🇿';
  if (codeEl) codeEl.textContent = state.lang.toUpperCase();
  $$('#langMenu .lang-opt').forEach((o) => o.classList.toggle('is-current', o.dataset.lang === state.lang));
}

// ---------- Loader hide ----------
window.addEventListener('load', () => {
  setTimeout(() => $('#loader')?.classList.add('hide'), 300);
});

// ---------- Floating bg beans ----------
(function spawnBeans() {
  const field = $('#beanField');
  if (!field) return;
  const N = Math.min(14, Math.max(6, Math.floor(window.innerWidth / 100)));
  for (let i = 0; i < N; i++) {
    const b = document.createElement('div');
    b.className = 'bean';
    const size = 8 + Math.random() * 18;
    b.style.cssText = `left:${Math.random()*100}%;width:${size}px;height:${size*1.4}px;animation-duration:${15+Math.random()*20}s;animation-delay:-${Math.random()*20}s;opacity:${0.05+Math.random()*0.15};`;
    field.appendChild(b);
  }
})();

// ---------- Nav scroll + toggle ----------
const nav = $('#nav');
const navLinks = $('#navLinks');
const navToggle = $('#navToggle');

window.addEventListener('scroll', () => {
  if (nav) nav.classList.toggle('scrolled', window.scrollY > 30);
}, { passive: true });

navToggle?.addEventListener('click', () => {
  if (!navLinks) return;
  navLinks.classList.toggle('open');
  navToggle.classList.toggle('open');
});
$$('#navLinks a').forEach((a) =>
  a.addEventListener('click', () => {
    if (navLinks) navLinks.classList.remove('open');
    if (navToggle) navToggle.classList.remove('open');
  })
);

// ---------- Reveal on scroll ----------
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (e.isIntersecting) {
      e.target.classList.add('in');
      revealObserver.unobserve(e.target);
    }
  });
}, { threshold: 0, rootMargin: '0px 0px -10% 0px' });
$$('.reveal').forEach((el) => revealObserver.observe(el));

// ---------- Tabs ----------
function renderTabs() {
  const tabsEl = $('#menuTabs');
  if (!tabsEl) return;
  const all = [{ id: 'all', name: { ru: t('menu.all'), uz: t('menu.all') }, icon: '✨' }, ...state.categories];
  tabsEl.innerHTML = all.map((c) => `
    <button class="menu-tab ${c.id === state.cat ? 'active' : ''}" data-cat="${c.id}">
      <span class="tab-icon">${c.icon || ''}</span>${catName(c)}
    </button>`).join('');
  $$('.menu-tab', tabsEl).forEach((btn) =>
    btn.addEventListener('click', () => {
      state.cat = btn.dataset.cat;
      renderTabs();
      renderMenu();
    })
  );
}

// ---------- Menu grid ----------
function renderMenu() {
  const gridEl = $('#menuGrid');
  const emptyEl = $('#menuEmpty');
  if (!gridEl || !emptyEl) return;
  const term = state.search.trim().toLowerCase();
  const items = state.products.filter((p) => {
    const okCat = state.cat === 'all' || p.category_id === state.cat;
    const hay = (productName(p) + ' ' + productDesc(p)).toLowerCase();
    return okCat && (!term || hay.includes(term));
  });

  if (!items.length) {
    gridEl.innerHTML = '';
    emptyEl.hidden = false;
    return;
  }
  emptyEl.hidden = true;

  gridEl.innerHTML = items.map((p, i) => {
    const sizes = p.sizes.map((s, idx) => `
      <button class="price-pill ${idx === 0 ? 'active' : ''}" data-size="${s.label}" data-price="${s.price}">
        <span class="size">${sizeLabel(s)}</span>
        <span class="amount">${(s.price/1000).toFixed(0)}k</span>
      </button>`).join('');
    const tag = productTag(p);
    return `
      <article class="menu-card" data-id="${p.id}" style="animation-delay:${Math.min(i, 12) * 40}ms">
        ${tag ? `<span class="menu-card-badge">${tag}</span>` : ''}
        <div class="menu-card-image">
          <img src="${p.img}" alt="${productName(p)}" loading="lazy" onerror="this.style.opacity=0.3"/>
          <button class="menu-card-eye" aria-label="${t('menu.details')}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        <div class="menu-card-body">
          <h3 class="menu-card-name">${productName(p)}</h3>
          <p class="menu-card-desc">${productDesc(p)}</p>
          <div class="menu-prices">${sizes}</div>
          <div class="menu-card-foot">
            <span class="selected-price">${fmt(p.sizes[0].price)}</span>
            <button class="add-btn" aria-label="${t('menu.add')}">+</button>
          </div>
        </div>
      </article>`;
  }).join('');

  $$('.menu-card', gridEl).forEach((card) => {
    const id = card.dataset.id;
    const product = state.products.find((p) => p.id === id);
    const pills = $$('.price-pill', card);
    const priceEl = $('.selected-price', card);

    pills.forEach((p) => p.addEventListener('click', (e) => {
      e.stopPropagation();
      pills.forEach((x) => x.classList.remove('active'));
      p.classList.add('active');
      priceEl.textContent = fmt(parseInt(p.dataset.price, 10));
    }));

    $('.add-btn', card).addEventListener('click', (e) => {
      e.stopPropagation();
      const active = pills.find((p) => p.classList.contains('active'));
      addToCart(product, active.dataset.size, parseInt(active.dataset.price, 10));
      card.classList.remove('pop'); void card.offsetWidth; card.classList.add('pop');
    });

    // open detail on card / eye click
    const openDetail = (e) => { e.stopPropagation(); showProduct(product); };
    $('.menu-card-image', card).addEventListener('click', openDetail);
    $('.menu-card-name', card).addEventListener('click', openDetail);
    $('.menu-card-desc', card).addEventListener('click', openDetail);
  });
}

// ---------- Search ----------
$('#menuSearch')?.addEventListener('input', (e) => {
  state.search = e.target.value;
  renderMenu();
});

// ---------- Product detail modal ----------
const productModal = $('#productModal');
function showProduct(p) {
  state.current = p;
  state.currentSize = p.sizes[0];

  $('#pmImg').src = p.img;
  $('#pmImg').alt = productName(p);
  $('#pmName').textContent = productName(p);
  $('#pmDesc').textContent = productDesc(p);

  const tag = productTag(p);
  const tagEl = $('#pmTag');
  if (tag) { tagEl.textContent = tag; tagEl.hidden = false; } else { tagEl.hidden = true; }

  const ingList = productIng(p);
  $('#pmIngredients').innerHTML = ingList.length
    ? ingList.map((x) => `<li><span class="dot-i"></span>${x}</li>`).join('')
    : `<li class="dim">—</li>`;

  $('#pmSizes').innerHTML = p.sizes.map((s, i) => `
    <button class="pm-size ${i === 0 ? 'active' : ''}" data-i="${i}">
      <span class="pm-size-label">${sizeLabel(s)}</span>
      <span class="pm-size-price">${fmt(s.price)}</span>
    </button>`).join('');
  $('#pmPrice').textContent = fmt(p.sizes[0].price);

  $$('#pmSizes .pm-size').forEach((btn) =>
    btn.addEventListener('click', () => {
      const i = parseInt(btn.dataset.i, 10);
      state.currentSize = p.sizes[i];
      $$('#pmSizes .pm-size').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      $('#pmPrice').textContent = fmt(state.currentSize.price);
    })
  );

  productModal.classList.add('show');
}
$('#productClose')?.addEventListener('click', () => productModal?.classList.remove('show'));
productModal?.addEventListener('click', (e) => { if (e.target === productModal) productModal.classList.remove('show'); });
$('#pmAdd')?.addEventListener('click', () => {
  if (!state.current || !state.currentSize) return;
  addToCart(state.current, state.currentSize.label, state.currentSize.price);
  productModal?.classList.remove('show');
});

// ---------- Cart ----------
const cartBtn      = $('#cartBtn');
const cartDrawer   = $('#cartDrawer');
const cartBackdrop = $('#cartBackdrop');
const cartCountEl  = $('#cartCount');
const cartBody     = $('#cartBody');
const cartEmpty    = $('#cartEmpty');
const cartTotalEl  = $('#cartTotal');
const checkoutBtn  = $('#checkoutBtn');
const cartNoteEl   = $('#cartNote');

function openCart()  { cartDrawer.classList.add('open'); cartBackdrop.classList.add('open'); }
function closeCart() { cartDrawer.classList.remove('open'); cartBackdrop.classList.remove('open'); }
if (cartBtn && cartDrawer && cartBackdrop) {
  cartBtn.addEventListener('click', openCart);
  $('#cartClose')?.addEventListener('click', closeCart);
  cartBackdrop.addEventListener('click', closeCart);
}

function addToCart(product, size, price) {
  const key = `${product.id}|${size}`;
  const existing = state.cart.find((c) => c.key === key);
  if (existing) existing.qty += 1;
  else state.cart.push({ key, id: product.id, size, price, qty: 1 });
  saveCart();
  renderCart();
  toast(t('toast.added', { name: productName(product) }));
  cartCountEl.classList.add('bump');
  setTimeout(() => cartCountEl.classList.remove('bump'), 300);
}
function changeQty(key, delta) {
  const it = state.cart.find((c) => c.key === key);
  if (!it) return;
  it.qty += delta;
  if (it.qty <= 0) state.cart = state.cart.filter((c) => c.key !== key);
  saveCart();
  renderCart();
}

function renderCart() {
  if (!cartCountEl || !cartTotalEl || !checkoutBtn || !cartBody || !cartEmpty) return;
  const count = state.cart.reduce((a, b) => a + b.qty, 0);
  const total = state.cart.reduce((a, b) => a + b.price * b.qty, 0);

  cartCountEl.textContent = count;
  cartCountEl.classList.toggle('show', count > 0);
  cartTotalEl.textContent = fmt(total);
  checkoutBtn.disabled = count === 0;

  if (!state.cart.length) {
    cartBody.innerHTML = '';
    cartBody.appendChild(cartEmpty);
    return;
  }

  cartBody.innerHTML = state.cart.map((c) => {
    const product = state.products.find((p) => p.id === c.id) || { name: { ru: c.id, uz: c.id }, img: '' };
    return `
      <div class="cart-item" data-key="${c.key}">
        <div class="cart-item-img" style="background-image:url('${product.img}')"></div>
        <div class="cart-item-info">
          <div class="cart-item-name">${productName(product)}</div>
          <div class="cart-item-meta">${c.size}${/^\d+$/.test(c.size) ? ' ' + t('curr.ml') : ''} · ${fmt(c.price)}</div>
          <div class="cart-item-controls">
            <div class="qty">
              <button data-act="dec">−</button>
              <span>${c.qty}</span>
              <button data-act="inc">+</button>
            </div>
            <div class="cart-item-price">${fmt(c.price * c.qty)}</div>
          </div>
        </div>
      </div>`;
  }).join('');

  $$('.cart-item', cartBody).forEach((row) => {
    const key = row.dataset.key;
    $('[data-act="inc"]', row).addEventListener('click', () => changeQty(key, +1));
    $('[data-act="dec"]', row).addEventListener('click', () => changeQty(key, -1));
  });
}

// ---------- Checkout ----------
checkoutBtn?.addEventListener('click', async () => {
  if (!state.cart.length) return;
  checkoutBtn.disabled = true;
  const original = checkoutBtn.textContent;
  checkoutBtn.textContent = t('cart.sending');

  try {
    // enrich items with names in chosen lang
    const itemsForServer = state.cart.map((c) => {
      const p = state.products.find((x) => x.id === c.id);
      return {
        id: c.id,
        name: p ? productName(p) : c.id,
        size: c.size,
        price: c.price,
        qty: c.qty,
      };
    });

    const res = await fetch('/api/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: itemsForServer,
        total: state.cart.reduce((a, b) => a + b.price * b.qty, 0),
        note: cartNoteEl.value || '',
        table: state.table,
        lang: state.lang,
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'err');

    state.cart = [];
    cartNoteEl.value = '';
    saveCart();
    renderCart();
    closeCart();
    showOrderModal(data.order_id, data.eta_min || 7);
  } catch (err) {
    toast(t('toast.error'));
  } finally {
    checkoutBtn.disabled = state.cart.length === 0;
    checkoutBtn.textContent = original;
  }
});

// ---------- Order modal ----------
const orderModal = $('#orderModal');
$('#modalClose')?.addEventListener('click', () => orderModal?.classList.remove('show'));
function showOrderModal(id, eta) {
  if (!orderModal) return;
  $('#orderId').textContent = '#' + id;
  $('#orderEtaText').innerHTML = t('ord.eta', { eta: `<strong>${eta}</strong>` });
  orderModal.classList.add('show');
}

// ---------- Toast ----------
const toastEl = $('#toast');
let toastTimer;
function toast(msg) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2200);
}

// ============================================
// LANGUAGE SWITCHER — hover-to-commit with ring loader
// ============================================
(function initLangSwitcher() {
  const sw = $('#langSwitch');
  const menu = $('#langMenu');
  if (!sw) return;

  let closeTimer;
  const open  = () => { clearTimeout(closeTimer); sw.classList.add('open'); menu.setAttribute('aria-hidden', 'false'); };
  const close = () => { closeTimer = setTimeout(() => { sw.classList.remove('open'); menu.setAttribute('aria-hidden', 'true'); }, 180); };

  sw.addEventListener('mouseenter', open);
  sw.addEventListener('mouseleave', close);
  $('#langCurrent').addEventListener('click', (e) => {
    e.preventDefault();
    sw.classList.toggle('open');
  });

  $$('#langMenu .lang-opt').forEach((opt) => {
    const lang = opt.dataset.lang;
    opt.addEventListener('click', () => {
      if (lang !== state.lang) switchLanguage(lang);
      sw.classList.remove('open');
    });
  });
})();

function switchLanguage(lang) {
  if (lang === state.lang || !['ru', 'uz'].includes(lang)) return;
  const overlay = $('#langOverlay');
  overlay?.classList.add('show');

  setTimeout(() => {
    state.lang = lang;
    body.dataset.lang = lang;
    // notify server (optional, also persisted in session for next page load)
    fetch(window.location.pathname + '?lang=' + lang).catch(() => {});

    applyI18n();
    renderTabs();
    renderMenu();
    renderCart();

    // close dropdown
    $('#langSwitch')?.classList.remove('open');

    setTimeout(() => overlay?.classList.remove('show'), 280);
  }, 350);
}

// ============================================
// BOOTSTRAP — load i18n + menu, then render
// ============================================
(async function boot() {
  const initialI18n = parseJsonScript('initialI18nData', {});
  const initialMenu = parseJsonScript('initialMenuData', { categories: [], products: [] });

  state.i18n = initialI18n;
  state.categories = initialMenu.categories || [];
  state.products = initialMenu.products || [];
  applyI18n();
  renderTabs();
  renderMenu();
  renderCart();

  try {
    const [i18nRes, menuRes] = await Promise.all([
      fetch('/api/i18n').then((r) => r.json()),
      fetch('/api/menu').then((r) => r.json()),
    ]);
    state.i18n = i18nRes;
    state.categories = menuRes.categories;
    state.products = menuRes.products;
  } catch (e) {
    console.error('Failed to load menu', e);
  }
  applyI18n();
  renderTabs();
  renderMenu();
  renderCart();
})();
