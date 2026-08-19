document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('adminMenuToggle');
    const sidebar = document.getElementById('adminSidebar');
    const overlay = document.getElementById('adminOverlay');

    function openSidebar() {
        sidebar.classList.add('open');
        overlay.classList.add('show');
    }
    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
    }

    if (toggle) {
        toggle.addEventListener('click', function () {
            if (sidebar.classList.contains('open')) closeSidebar();
            else openSidebar();
        });
    }
    if (overlay) overlay.addEventListener('click', closeSidebar);

    // Auto-dismiss flashes
    document.querySelectorAll('.flash').forEach(function (f) {
        setTimeout(function () {
            f.style.opacity = '0';
            setTimeout(function () { f.remove(); }, 400);
        }, 4500);
    });

    // Confirm delete
    document.querySelectorAll('[data-confirm]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm(btn.getAttribute('data-confirm'))) e.preventDefault();
        });
    });
});
