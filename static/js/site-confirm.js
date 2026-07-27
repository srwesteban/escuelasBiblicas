/*
 * Confirmación personalizada (reemplaza confirm() nativo del navegador) con el
 * mismo estilo del resto de la app.
 *
 * Uso automático: agregá data-confirm-message="..." a un <form> y el envío
 * queda interceptado hasta que la persona confirme en el cuadro.
 *   <form method="post" data-confirm-message="¿Eliminar esta escuela?">
 *
 * Atributos opcionales: data-confirm-title, data-confirm-label ("Eliminar" por defecto).
 *
 * Uso manual: SiteConfirm.ask('¿Seguro?', {title: '...', confirmLabel: '...'})
 *             devuelve una Promise<boolean>.
 */
(function (window, document) {
    'use strict';

    var STYLE_ID = 'site-confirm-styles';

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        var style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
            '.site-confirm-dialog{border:none;padding:0;border-radius:1rem;max-width:24rem;width:calc(100% - 2rem);',
            'box-shadow:0 25px 50px -12px rgba(0,0,0,0.35);background:hsl(var(--background));color:hsl(var(--foreground));}',
            '.site-confirm-dialog::backdrop{background:rgba(15,23,42,0.45);}',
            '.site-confirm-body{padding:1.5rem;}',
            '.site-confirm-title{margin:0 0 0.5rem;font-size:1.05rem;font-weight:700;color:hsl(var(--foreground));}',
            '.site-confirm-message{margin:0;font-size:0.9rem;line-height:1.5;color:hsl(var(--foreground) / 0.75);}',
            '.site-confirm-actions{display:flex;justify-content:flex-end;gap:0.6rem;margin-top:1.5rem;}',
            '.site-confirm-actions .btn-outline,.site-confirm-actions .site-confirm-btn-danger,.site-confirm-actions .btn-primary{',
            'padding:0.55rem 1.1rem;font-size:0.875rem;font-weight:500;cursor:pointer;}',
            '.site-confirm-btn-danger{border-radius:var(--radius);border:1px solid #fecaca;background:#fff;color:#b91c1c;transition:background 0.15s ease;}',
            '.site-confirm-btn-danger:hover{background:#fef2f2;}'
        ].join('');
        document.head.appendChild(style);
    }

    var dom = null;

    function buildDom() {
        var dialog = document.createElement('dialog');
        dialog.className = 'site-confirm-dialog';
        dialog.setAttribute('aria-labelledby', 'site-confirm-title');
        dialog.innerHTML = [
            '<div class="site-confirm-body">',
            '<h3 class="site-confirm-title" id="site-confirm-title"></h3>',
            '<p class="site-confirm-message"></p>',
            '<div class="site-confirm-actions">',
            '<button type="button" class="btn-outline site-confirm-cancel"></button>',
            '<button type="button" class="site-confirm-confirm"></button>',
            '</div></div>'
        ].join('');
        document.body.appendChild(dialog);
        dialog.addEventListener('click', function (ev) {
            var rect = dialog.getBoundingClientRect();
            var inside = ev.clientX >= rect.left && ev.clientX <= rect.right && ev.clientY >= rect.top && ev.clientY <= rect.bottom;
            if (!inside) dialog.close();
        });
        return {
            dialog: dialog,
            title: dialog.querySelector('.site-confirm-title'),
            message: dialog.querySelector('.site-confirm-message'),
            confirmBtn: dialog.querySelector('.site-confirm-confirm'),
            cancelBtn: dialog.querySelector('.site-confirm-cancel'),
        };
    }

    function ask(message, opts) {
        opts = opts || {};
        ensureStyles();
        if (!dom) dom = buildDom();

        return new Promise(function (resolve) {
            dom.title.textContent = opts.title || 'Confirmar acción';
            dom.message.textContent = message || '¿Estás seguro?';
            dom.confirmBtn.textContent = opts.confirmLabel || 'Eliminar';
            dom.confirmBtn.className = opts.danger === false ? 'btn-primary' : 'site-confirm-btn-danger';
            dom.cancelBtn.textContent = opts.cancelLabel || 'Cancelar';

            var settled = false;
            function finish(result) {
                if (settled) return;
                settled = true;
                dom.confirmBtn.removeEventListener('click', onConfirm);
                dom.cancelBtn.removeEventListener('click', onCancel);
                dom.dialog.removeEventListener('close', onClose);
                resolve(result);
            }
            function onConfirm() { dom.dialog.close(); finish(true); }
            function onCancel() { dom.dialog.close(); finish(false); }
            function onClose() { finish(false); }

            dom.confirmBtn.addEventListener('click', onConfirm);
            dom.cancelBtn.addEventListener('click', onCancel);
            dom.dialog.addEventListener('close', onClose);

            dom.dialog.showModal();
            dom.confirmBtn.focus();
        });
    }

    function wireForms(root) {
        (root || document).querySelectorAll('form[data-confirm-message]').forEach(function (form) {
            if (form.dataset.confirmWired === 'true') return;
            form.dataset.confirmWired = 'true';
            form.addEventListener('submit', function (ev) {
                if (form.dataset.confirmSkip === 'true') {
                    form.dataset.confirmSkip = '';
                    return;
                }
                ev.preventDefault();
                ask(form.getAttribute('data-confirm-message'), {
                    title: form.getAttribute('data-confirm-title') || undefined,
                    confirmLabel: form.getAttribute('data-confirm-label') || undefined,
                }).then(function (ok) {
                    if (!ok) return;
                    form.dataset.confirmSkip = 'true';
                    if (form.requestSubmit) form.requestSubmit();
                    else form.submit();
                });
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { wireForms(); });
    } else {
        wireForms();
    }

    window.SiteConfirm = { ask: ask, wireForms: wireForms };
})(window, document);
