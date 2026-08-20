// Auto-inject CSRF token into every POST form (forms are hand-written HTML)
(function () {
    const token = document.querySelector('meta[name="csrf-token"]');
    if (!token) return;
    const csrf = token.getAttribute('content');
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || form.tagName !== 'FORM') return;
        if (form.method && form.method.toLowerCase() !== 'post') return;
        if (form.querySelector('input[name="csrf_token"]')) return;
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrf_token';
        input.value = csrf;
        form.appendChild(input);
    });
})();

// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('mobileToggle');
    const nav = document.getElementById('mainNav');
    if (toggle && nav) {
        toggle.addEventListener('click', function () {
            nav.classList.toggle('open');
        });
        // Close menu when clicking a link
        nav.querySelectorAll('a').forEach(function (a) {
            a.addEventListener('click', function () {
                nav.classList.remove('open');
            });
        });
    }

    // Auto-dismiss flash messages
    document.querySelectorAll('.flash').forEach(function (flash) {
        setTimeout(function () {
            flash.style.opacity = '0';
            setTimeout(function () { flash.remove(); }, 400);
        }, 4500);
    });

    // Cart add buttons (AJAX)
    document.querySelectorAll('[data-add-to-cart]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const plantId = btn.getAttribute('data-plant-id');
            const qtyInput = document.querySelector('[data-qty-for="' + plantId + '"]');
            const qty = qtyInput ? parseInt(qtyInput.value) || 1 : 1;
            addToCart(plantId, qty, btn);
        });
    });

    // Quantity steppers on product page
    document.querySelectorAll('[data-step]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const input = document.getElementById(btn.getAttribute('data-target'));
            if (!input) return;
            let val = parseInt(input.value) || 1;
            const step = parseInt(btn.getAttribute('data-step'));
            const min = parseInt(input.getAttribute('min')) || 1;
            const max = parseInt(input.getAttribute('max')) || 999;
            val = Math.min(max, Math.max(min, val + step));
            input.value = val;
        });
    });
});

// ---------- Banner slider (supports multiple sliders via id suffix) ----------
function bannerSliderEl(suffix) {
    return document.getElementById('bannerSlider' + (suffix || ''));
}

function bannerMove(dir, suffix) {
    const slider = bannerSliderEl(suffix);
    if (!slider) return;
    const track = slider.querySelector('.banner-track');
    const slides = slider.querySelectorAll('.banner-slide');
    if (!track || slides.length < 2) return;
    let idx = parseInt(slider.getAttribute('data-banner-index') || '0', 10);
    idx = (idx + dir + slides.length) % slides.length;
    slider.setAttribute('data-banner-index', idx);
    track.style.transform = 'translateX(-' + (idx * 100) + '%)';
    updateBannerDots(slider, idx);
}

function bannerGo(idx, suffix) {
    const slider = bannerSliderEl(suffix);
    if (!slider) return;
    const track = slider.querySelector('.banner-track');
    const slides = slider.querySelectorAll('.banner-slide');
    if (!track || slides.length < 2) return;
    slider.setAttribute('data-banner-index', idx);
    track.style.transform = 'translateX(-' + (idx * 100) + '%)';
    updateBannerDots(slider, idx);
}

function updateBannerDots(slider, idx) {
    const dots = slider.querySelectorAll('.banner-dot');
    dots.forEach(function (dot, i) {
        dot.classList.toggle('active', i === idx);
    });
}

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

function addToCart(plantId, qty, btn) {
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    fetch('/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'plant_id=' + encodeURIComponent(plantId) + '&quantity=' + encodeURIComponent(qty) + '&csrf_token=' + encodeURIComponent(getCsrfToken())
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                showToast(data.message, 'success');
                updateCartBadge(data.cart_count);
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(function () { showToast('Something went wrong.', 'error'); })
        .finally(function () {
            btn.disabled = false;
            btn.innerHTML = original;
        });
}

function updateCartBadge(count) {
    const badge = document.querySelector('.cart-btn .badge');
    if (count > 0) {
        if (badge) { badge.textContent = count; }
        else {
            const cartBtn = document.querySelector('.cart-btn');
            if (cartBtn) {
                const b = document.createElement('span');
                b.className = 'badge';
                b.textContent = count;
                cartBtn.appendChild(b);
            }
        }
    } else if (badge) {
        badge.remove();
    }
}

function showToast(message, type) {
    const container = document.querySelector('.flash-container');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'flash flash-' + (type || 'info');
    div.innerHTML = '<span>' + message + '</span><button class="flash-close" onclick="this.parentElement.remove()">&times;</button>';
    container.appendChild(div);
    setTimeout(function () {
        div.style.opacity = '0';
        setTimeout(function () { div.remove(); }, 400);
    }, 4500);
}

function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}
