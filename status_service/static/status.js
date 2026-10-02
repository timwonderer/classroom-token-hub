/* Progressive enhancement for the status pages. Every page is complete without
   it: times render in UTC on the server, and the operator form submits as-is. */
(function () {
    'use strict';

    // ── Reader-local time: <time datetime="…Z" data-local="time|datetime|date"> ──
    var FORMATS = {
        time: { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' },
        datetime: { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' },
        date: { month: 'short', day: 'numeric', year: 'numeric' }
    };

    function localise(root) {
        root.querySelectorAll('time[data-local]').forEach(function (el) {
            var moment = new Date(el.getAttribute('datetime'));
            var format = FORMATS[el.getAttribute('data-local')];
            if (isNaN(moment.getTime()) || !format) { return; }
            try {
                el.textContent = new Intl.DateTimeFormat(undefined, format).format(moment);
            } catch (error) { /* keep the server's UTC text */ }
        });
    }

    function utcText(moment) {
        return moment.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
    }

    function offsetLabel(minutes) {
        var sign = minutes >= 0 ? '+' : '−';
        var abs = Math.abs(minutes);
        var hours = Math.floor(abs / 60);
        var rest = abs % 60;
        return 'UTC' + (abs ? sign + hours + (rest ? ':' + String(rest).padStart(2, '0') : '') : '');
    }

    // ── Operator console: local time in, UTC echoed back; live preview ──
    function enhanceForm(form) {
        var offset = -new Date().getTimezoneOffset();
        var tzField = form.querySelector('[data-tz-offset]');
        if (tzField) { tzField.value = String(offset); }
        form.querySelectorAll('[data-tz-label]').forEach(function (el) {
            el.textContent = '(your local time, ' + offsetLabel(offset) + ')';
        });

        form.querySelectorAll('[data-time-echo]').forEach(function (input) {
            var echo = document.getElementById(input.getAttribute('data-time-echo'));
            function update() {
                var moment = input.value ? new Date(input.value) : null;
                echo.textContent = moment && !isNaN(moment.getTime()) ? '= ' + utcText(moment) : '';
            }
            input.addEventListener('input', update);
            update();
        });

        var custom = form.querySelector('[data-custom-time]');
        function syncCustom() {
            var choice = form.querySelector('input[name="next_update_choice"]:checked');
            if (custom) { custom.hidden = !choice || choice.value !== 'custom'; }
        }

        form.querySelectorAll('[data-count]').forEach(function (field) {
            var counter = document.getElementById(field.getAttribute('data-count'));
            function update() { counter.textContent = field.value.length + ' / ' + field.maxLength; }
            field.addEventListener('input', update);
            update();
        });

        var stages = JSON.parse(form.getAttribute('data-stages') || '{}');
        var areas = JSON.parse(form.getAttribute('data-areas') || '{}');
        var card = document.querySelector('[data-preview]');

        function checked(name) {
            var el = form.querySelector('input[name="' + name + '"]:checked');
            return el ? el.value : '';
        }

        function preview() {
            syncCustom();
            if (!card) { return; }
            var stage = stages[checked('state')] || stages.AWARE;
            var area = areas[checked('capability')] || areas.service;
            var headline = area.name + ': ' + stage.headline;
            card.querySelector('[data-preview-headline]').textContent = headline;
            card.className = 'notice notice--' + stage.tone;
            var chip = card.querySelector('[data-preview-chip] .chip');
            chip.className = 'chip chip--' + stage.tone;
            chip.querySelector('.status-icon').textContent = stage.icon;
            chip.lastChild.textContent = stage.label;
            var impact = form.querySelector('[data-preview-source="impact"]').value;
            var action = form.querySelector('[data-preview-source="action"]').value;
            card.querySelector('[data-preview-impact]').textContent = impact || 'Describe what people are seeing.';
            card.querySelector('[data-preview-action]').textContent = action || 'Tell people what to do.';
            var next = card.querySelector('[data-preview-next]');
            var choice = checked('next_update_choice');
            var minutes = { '30': 30, '60': 60, '120': 120 }[choice];
            var when = null;
            if (minutes) { when = new Date(Date.now() + minutes * 60000); }
            if (choice === 'custom') {
                var value = form.querySelector('#next_update_at').value;
                when = value ? new Date(value) : null;
            }
            next.textContent = '';
            if (when && !isNaN(when.getTime())) {
                var label = document.createElement('b');
                label.textContent = 'Next update';
                next.appendChild(label);
                next.appendChild(document.createTextNode(' by ' + new Intl.DateTimeFormat(undefined, FORMATS.time).format(when)));
            } else {
                next.textContent = 'Next update time not set yet';
            }
        }

        form.addEventListener('input', preview);
        form.addEventListener('change', preview);
        preview();
    }

    document.addEventListener('DOMContentLoaded', function () {
        localise(document);
        document.querySelectorAll('[data-current-year]').forEach(function (el) {
            el.textContent = String(new Date().getFullYear());
        });
        document.querySelectorAll('form[data-notice-form]').forEach(enhanceForm);
    });
}());
