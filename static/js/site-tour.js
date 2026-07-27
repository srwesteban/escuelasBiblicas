/*
 * Tutorial guiado reutilizable (recuadro animado + texto, sin voz).
 * Uso: SiteTour.start([{ selector: '#id', title: '...', text: '...' }, { title: '...', text: '...' }]);
 * Un paso sin `selector` se muestra centrado, sin resaltar nada.
 */
(function (window, document) {
    'use strict';

    var STYLE_ID = 'site-tour-styles';

    function ensureStyles() {
        if (document.getElementById(STYLE_ID)) return;
        var style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
            '.tour-backdrop{position:fixed;inset:0;background:rgba(28,25,23,.6);z-index:9998;animation:tour-fade-in .2s ease;}',
            '.tour-highlight{position:relative;z-index:9999;border-radius:.9rem;box-shadow:0 0 0 4px rgba(217,119,6,.55),0 12px 32px rgba(0,0,0,.35);animation:tour-pulse 1.6s ease-in-out infinite;}',
            '.tour-tooltip{position:fixed;z-index:10000;max-width:20rem;background:#fff;border-radius:.9rem;padding:1rem 1.1rem;box-shadow:0 20px 45px rgba(0,0,0,.3);animation:tour-pop-in .18s ease;}',
            '.tour-tooltip-step{font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#b45309;margin:0 0 .25rem;}',
            '.tour-tooltip-title{font-size:1rem;font-weight:700;color:#1c1917;margin:0 0 .35rem;}',
            '.tour-tooltip-text{font-size:.875rem;line-height:1.4;color:#44403c;margin:0;}',
            '.tour-tooltip-actions{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:.9rem;}',
            '.tour-tooltip-nav{display:flex;gap:.4rem;}',
            '.tour-btn{border-radius:.6rem;padding:.4rem .75rem;font-size:.8rem;font-weight:600;cursor:pointer;border:1px solid transparent;}',
            '.tour-btn-primary{background:#1c1917;color:#fff;}',
            '.tour-btn-outline{background:#fff;border-color:#d6d3d1;color:#1c1917;}',
            '.tour-btn-ghost{background:transparent;color:#78716c;}',
            '.tour-btn-ghost:hover{color:#44403c;text-decoration:underline;}',
            '@keyframes tour-fade-in{from{opacity:0}to{opacity:1}}',
            '@keyframes tour-pop-in{from{opacity:0;transform:translateY(6px) scale(.98)}to{opacity:1;transform:translateY(0) scale(1)}}',
            '@keyframes tour-pulse{0%,100%{box-shadow:0 0 0 4px rgba(217,119,6,.55),0 12px 32px rgba(0,0,0,.35)}50%{box-shadow:0 0 0 8px rgba(217,119,6,.3),0 12px 32px rgba(0,0,0,.35)}}'
        ].join('\n');
        document.head.appendChild(style);
    }

    function buildDom() {
        var backdrop = document.createElement('div');
        backdrop.className = 'tour-backdrop';
        backdrop.hidden = true;

        var tooltip = document.createElement('div');
        tooltip.className = 'tour-tooltip';
        tooltip.setAttribute('role', 'dialog');
        tooltip.hidden = true;
        tooltip.innerHTML = [
            '<p class="tour-tooltip-step"></p>',
            '<h3 class="tour-tooltip-title"></h3>',
            '<p class="tour-tooltip-text"></p>',
            '<div class="tour-tooltip-actions">',
            '<button type="button" class="tour-btn tour-btn-ghost" data-tour-skip>Saltar</button>',
            '<div class="tour-tooltip-nav">',
            '<button type="button" class="tour-btn tour-btn-outline" data-tour-prev>Atrás</button>',
            '<button type="button" class="tour-btn tour-btn-primary" data-tour-next>Siguiente</button>',
            '</div></div>'
        ].join('');

        document.body.appendChild(backdrop);
        document.body.appendChild(tooltip);
        return { backdrop: backdrop, tooltip: tooltip };
    }

    var dom = null;
    var steps = [];
    var idx = 0;
    var currentEl = null;

    function clearHighlight() {
        if (currentEl) {
            currentEl.classList.remove('tour-highlight');
            currentEl = null;
        }
    }

    function positionTooltip(target) {
        var vw = window.innerWidth;
        var vh = window.innerHeight;
        var tooltip = dom.tooltip;
        if (!target) {
            tooltip.style.top = (vh / 2 - 90) + 'px';
            tooltip.style.left = (vw / 2 - 160) + 'px';
            return;
        }
        var rect = target.getBoundingClientRect();
        var top = rect.bottom + 14;
        var left = rect.left;
        if (top + 190 > vh) top = Math.max(12, rect.top - 190);
        if (left + 320 > vw) left = Math.max(12, vw - 332);
        tooltip.style.top = top + 'px';
        tooltip.style.left = left + 'px';
    }

    function renderStep() {
        clearHighlight();
        var step = steps[idx];
        var target = step.selector ? document.querySelector(step.selector) : null;
        if (target) {
            if (typeof step.onEnter === 'function') step.onEnter(target);
            target.classList.add('tour-highlight');
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            currentEl = target;
        }
        dom.tooltip.querySelector('.tour-tooltip-step').textContent = 'Paso ' + (idx + 1) + ' de ' + steps.length;
        dom.tooltip.querySelector('.tour-tooltip-title').textContent = step.title;
        dom.tooltip.querySelector('.tour-tooltip-text').textContent = step.text;
        dom.tooltip.querySelector('[data-tour-prev]').style.visibility = idx === 0 ? 'hidden' : 'visible';
        dom.tooltip.querySelector('[data-tour-next]').textContent = idx === steps.length - 1 ? 'Terminar' : 'Siguiente';
        setTimeout(function () { positionTooltip(target); }, target ? 260 : 0);
    }

    function close() {
        clearHighlight();
        if (dom) {
            dom.backdrop.hidden = true;
            dom.tooltip.hidden = true;
        }
    }

    function next() {
        if (idx >= steps.length - 1) {
            close();
            return;
        }
        idx += 1;
        renderStep();
    }

    function prev() {
        if (idx === 0) return;
        idx -= 1;
        renderStep();
    }

    function start(newSteps) {
        if (!newSteps || !newSteps.length) return;
        ensureStyles();
        if (!dom) {
            dom = buildDom();
            dom.tooltip.querySelector('[data-tour-next]').addEventListener('click', next);
            dom.tooltip.querySelector('[data-tour-prev]').addEventListener('click', prev);
            dom.tooltip.querySelector('[data-tour-skip]').addEventListener('click', close);
            dom.backdrop.addEventListener('click', close);
            document.addEventListener('keydown', function (ev) {
                if (ev.key === 'Escape' && dom && !dom.backdrop.hidden) close();
            });
            window.addEventListener('resize', function () {
                if (dom && !dom.backdrop.hidden) positionTooltip(currentEl);
            });
        }
        steps = newSteps;
        idx = 0;
        dom.backdrop.hidden = false;
        dom.tooltip.hidden = false;
        renderStep();
    }

    window.SiteTour = { start: start, close: close };
})(window, document);
