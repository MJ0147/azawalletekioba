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

  if (document.getElementById('cart-drawer')) {
    _renderCartDrawer();
  }
}

function _cartTotalNgn() {
  return _cart.reduce((sum, i) => sum + ((Number(i.price) || 0) * (Number(i.qty) || 1)), 0);
}

function _renderCartDrawer() {
  const itemsEl = document.getElementById('cart-items');
  const totalEl = document.getElementById('cart-total-ngn');
  if (!itemsEl || !totalEl) return;

  if (!_cart.length) {
    itemsEl.innerHTML = '<p style="color:#666">Your cart is empty.</p>';
    totalEl.textContent = '₦0';
    return;
  }

  itemsEl.innerHTML = _cart.map(function (item) {
    const qty = Number(item.qty) || 1;
    const price = Number(item.price) || 0;
    const subtotal = price * qty;
    return '<div style="display:grid;gap:.35rem;border:1px solid #eee;border-radius:.65rem;padding:.65rem;margin-bottom:.6rem">'
      + '<div style="display:flex;justify-content:space-between;gap:.5rem">'
      + '<strong style="font-size:.9rem">' + String(item.name || 'Item') + '</strong>'
      + '<button type="button" onclick="removeFromCart(\'' + String(item.id) + '\')" style="background:none;border:none;color:#b91c1c;cursor:pointer;font-size:.8rem">Remove</button>'
      + '</div>'
      + '<div style="display:flex;justify-content:space-between;font-size:.85rem;color:#555">'
      + '<span>Qty: ' + qty + '</span><span>₦' + subtotal.toLocaleString() + '</span>'
      + '</div></div>';
  }).join('');

  totalEl.textContent = '₦' + _cartTotalNgn().toLocaleString();
}

function openCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  const backdrop = document.getElementById('cart-backdrop');
  if (!drawer || !backdrop) return;
  _renderCartDrawer();
  drawer.style.transform = 'translateX(0)';
  backdrop.style.display = 'block';
}

function closeCartDrawer() {
  const drawer = document.getElementById('cart-drawer');
  const backdrop = document.getElementById('cart-backdrop');
  if (!drawer || !backdrop) return;
  drawer.style.transform = 'translateX(100%)';
  backdrop.style.display = 'none';
}

function removeFromCart(productId) {
  _cart = _cart.filter(function (item) { return String(item.id) !== String(productId); });
  try { sessionStorage.setItem('ekioba-cart', JSON.stringify(_cart)); } catch (_) {}
  _updateCartBadge();
}

function clearCart() {
  _cart = [];
  try { sessionStorage.setItem('ekioba-cart', JSON.stringify(_cart)); } catch (_) {}
  _updateCartBadge();
}

function checkoutCart() {
  const total = _cartTotalNgn();
  if (total <= 0) {
    _showToast('Add items to cart first');
    return;
  }
  if (typeof window.openIdiaPayment !== 'function') {
    _showToast('Payment module is unavailable right now');
    return;
  }
  const cartSnapshot = _cart.map(function (item) {
    return {
      id: item.id,
      name: item.name,
      qty: Number(item.qty) || 1,
      price: Number(item.price) || 0,
    };
  });
  window.openIdiaPayment('cart', 'EKIOBA Cart Checkout', total, {
    isCartCheckout: true,
    cartItems: cartSnapshot,
    cartTotalNgn: total,
  });
  closeCartDrawer();
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

function _setActiveNavTab() {
  const links = Array.from(document.querySelectorAll('.nav-links a[href]'));
  if (!links.length) return;

  const path = window.location.pathname || '/';
  const hash = window.location.hash || '';

  links.forEach((link) => {
    const href = link.getAttribute('href') || '';
    let isActive = false;

    if (href === '/') {
      isActive = path === '/' && !hash;
    } else if (href.startsWith('/#')) {
      isActive = path === '/' && hash === href.slice(1);
    } else {
      isActive = path === href || path.startsWith(href + '/');
    }

    link.classList.toggle('active', isActive);
    if (isActive) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
}

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  _updateCartBadge();
  _setActiveNavTab();

  window.addEventListener('hashchange', _setActiveNavTab);
  document.querySelectorAll('.nav-links a[href^="/#"]').forEach((link) => {
    link.addEventListener('click', () => {
      // Let the browser update the hash first before recomputing active tab.
      setTimeout(_setActiveNavTab, 0);
    });
  });

  window.addToCart = addToCart;
  window.openCartDrawer = openCartDrawer;
  window.closeCartDrawer = closeCartDrawer;
  window.checkoutCart = checkoutCart;
  window.clearCart = clearCart;
  window.removeFromCart = removeFromCart;
  window.onCheckoutSuccess = function (context, data) {
    if (!context || !context.isCartCheckout) return;
    const orderRef = data && (data.order_id || data.reference) ? (data.order_id || data.reference) : 'created';
    clearCart();
    _showToast('Cart checkout ' + orderRef + ' started');
  };
});
