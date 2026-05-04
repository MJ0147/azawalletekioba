/* EKIOBA — frontend client-side logic */
'use strict';

// ── Cart ──────────────────────────────────────────────────────────────────
let _cart = [];

try {
  _cart = JSON.parse(sessionStorage.getItem('ekioba-cart') || '[]');
} catch (_) {
  _cart = [];
}

function addToCart(productId) {
  const dataEl = document.getElementById('products-json');
  if (!dataEl) return;

  let products = [];
  try { products = JSON.parse(dataEl.textContent); } catch (_) { return; }

  const product = products.find(p => String(p.id) === String(productId));
  if (!product) return;

  const existing = _cart.find(i => String(i.id) === String(productId));
  if (existing) {
    existing.qty += 1;
  } else {
    _cart.push({ id: product.id, name: product.name, price: product.price, qty: 1 });
  }

  try { sessionStorage.setItem('ekioba-cart', JSON.stringify(_cart)); } catch (_) {}
  _updateCartBadge();
  _showToast(product.name + ' added to cart');
}

function _updateCartBadge() {
  const badge = document.getElementById('cart-count');
  if (!badge) return;
  const total = _cart.reduce((sum, i) => sum + (i.qty || 1), 0);
  badge.textContent = String(total);
  badge.hidden = total === 0;
}

function _showToast(message) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.setAttribute('role', 'status');
  t.setAttribute('aria-live', 'polite');
  t.textContent = message;
  document.body.appendChild(t);
  requestAnimationFrame(() => t.classList.add('toast--visible'));
  setTimeout(() => {
    t.classList.remove('toast--visible');
    setTimeout(() => t.remove(), 350);
  }, 2400);
}

// ── Screen reader ─────────────────────────────────────────────────────────
function startReader() {
  const summary =
    document.querySelector('[data-reader-text]')?.dataset.readerText ||
    'Dashboard loaded. Market data is now live.';
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(summary));
}

function stopReader() {
  window.speechSynthesis.cancel();
}

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  _updateCartBadge();
});
