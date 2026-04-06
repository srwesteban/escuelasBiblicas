/**
 * Inputs con clase .input-cop-money: formato colombiano al escribir (2.000, 25.000,50).
 * Antes de enviar el formulario se normaliza a número para el servidor (2000, 25000.50).
 */
(function () {
    'use strict';

    function formatCopDisplay(str) {
        if (!str) return '';
        var s = String(str).replace(/[^\d,]/g, '');
        if (s === '') return '';

        var idx = s.indexOf(',');
        var intRaw;
        var decRaw = '';
        if (idx === -1) {
            intRaw = s;
        } else {
            intRaw = s.slice(0, idx);
            decRaw = s.slice(idx + 1).replace(/\D/g, '').slice(0, 2);
        }
        intRaw = intRaw.replace(/\D/g, '');
        if (intRaw.length > 15) intRaw = intRaw.slice(0, 15);

        if (intRaw === '' && decRaw === '') {
            return s.indexOf(',') !== -1 ? '0,' : '';
        }

        var intPart = intRaw.replace(/^0+(?=\d)/, '');
        if (intPart === '') intPart = '0';

        var intRev = intPart.split('').reverse().join('');
        var chunks = intRev.match(/.{1,3}/g) || [];
        var intFmt = chunks
            .map(function (c) {
                return c.split('').reverse().join('');
            })
            .reverse()
            .join('.');

        if (decRaw.length > 0 || (idx !== -1 && s.slice(-1) === ',')) {
            return intFmt + ',' + decRaw;
        }
        return intFmt;
    }

    function serverDecimalToDisplay(s) {
        if (!s && s !== 0) return '';
        s = String(s).trim().replace(',', '.');
        var m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(s);
        if (!m) return s;
        var w = m[1];
        var f = (m[2] || '').slice(0, 2);
        if (f && f !== '00') {
            return formatCopDisplay(w + ',' + f);
        }
        return formatCopDisplay(w);
    }

    function toServerNumberString(display) {
        if (!display || !String(display).trim()) return '';
        var s = String(display).trim();
        if (s.indexOf(',') !== -1) {
            return s.replace(/\./g, '').replace(',', '.');
        }
        var parts = s.split('.');
        if (parts.length === 1) return parts[0];
        var allNum = parts.every(function (p) {
            return /^\d+$/.test(p);
        });
        if (allNum && parts[parts.length - 1].length === 3) {
            return parts.join('');
        }
        if (parts.length === 2 && parts[parts.length - 1].length <= 2) {
            return parts[0] + '.' + parts[parts.length - 1];
        }
        return parts.join('');
    }

    function initInput(input) {
        if (input.value) {
            var v = input.value.trim();
            if (/^\d+(\.\d{1,2})?$/.test(v)) {
                input.value = serverDecimalToDisplay(v);
            } else if (/[\d.]/.test(v)) {
                input.value = formatCopDisplay(v.replace(/\./g, '').replace(',', ','));
            }
        }

        input.addEventListener('input', function () {
            var pos = this.selectionStart;
            var oldLen = this.value.length;
            var next = formatCopDisplay(this.value);
            if (next !== this.value) {
                this.value = next;
                var newLen = this.value.length;
                var end = Math.min(newLen, Math.max(0, pos + (newLen - oldLen)));
                try {
                    this.setSelectionRange(end, end);
                } catch (e) {
                    this.setSelectionRange(newLen, newLen);
                }
            }
        });

        input.addEventListener('blur', function () {
            if (this.value.trim() === '' || this.value === '0,') return;
            var n = formatCopDisplay(this.value);
            if (n !== this.value) this.value = n;
        });
    }

    function bindForm(form) {
        if (form.dataset.copMoneyBound) return;
        form.dataset.copMoneyBound = '1';
        form.addEventListener('submit', function () {
            form.querySelectorAll('input.input-cop-money').forEach(function (inp) {
                var raw = toServerNumberString(inp.value);
                inp.value = raw;
            });
        });
    }

    function run() {
        document.querySelectorAll('input.input-cop-money').forEach(function (inp) {
            initInput(inp);
            var form = inp.closest('form');
            if (form) bindForm(form);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
