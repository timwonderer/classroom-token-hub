"""Targeted rendered-state evidence, using the repository's Playwright/axe pattern."""
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright, TimeoutError

from build import CACHE, ROOT
from preview import Handler


def run():
    reports = {}
    screenshots = ROOT / 'output/playwright/docs-generator-proof'
    screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, site in [('hugo', CACHE / 'hugo/public'), ('zensical', CACHE / 'zensical/docs-site/build')]:
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(site)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}/docs/'
            states = {}
            network = []
            errors = []
            for mobile in (False, True):
                context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 844 if mobile else 1000})
                page = context.new_page()
                page.on('request', lambda request: network.append(request.url) if not request.url.startswith(base.split('/docs')[0]) else None)
                page.on('pageerror', lambda error: errors.append(str(error)))

                def audit(label):
                    page.add_script_tag(path=str(ROOT / 'tests/assets/axe-core.min.js'))
                    states[label] = {
                        'violations': page.evaluate("async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations"),
                        'overflow': page.evaluate('document.documentElement.scrollWidth > innerWidth'),
                    }

                mode = 'mobile' if mobile else 'desktop'
                for label, route in [('home', ''), ('catalog', 'documents/'),
                                     ('identity', 'DOMAIN/DOM-IDEN-001_CANONICAL_IDENTITY_MODEL/'),
                                     ('core', 'INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS/')]:
                    response = page.goto(base + route, wait_until='networkidle')
                    assert response.ok, route
                    audit(f'{mode}:{label}')
                    if label in ('home', 'catalog', 'identity'):
                        page.screenshot(path=str(screenshots / f'{name}-{mode}-{label}.png'), full_page=label != 'catalog')
                    if name == 'hugo':
                        brand = page.evaluate("""() => {
                            const token = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
                            const color = name => { const e = document.createElement('span'); e.style.color = `var(${name})`; document.body.append(e); const v = getComputedStyle(e).color; e.remove(); return v; };
                            return {background: getComputedStyle(document.body).backgroundColor === color('--background'),
                              headingWeight: getComputedStyle(document.querySelector('h1')).fontWeight === token(document.querySelector('.landing-welcome h1') ? '--weight-semibold' : '--weight-bold'),
                              hero: !document.querySelector('.landing-welcome h1') || getComputedStyle(document.querySelector('.landing-welcome h1')).color === color('--secondary'),
                              footer: getComputedStyle(document.querySelector('footer')).backgroundColor === color('--neutral-800')};
                        }""")
                        states[f'{mode}:{label}']['brand_tokens'] = brand
                        assert all(brand.values()), (label, brand)
                    if label == 'home':
                        states[f'{mode}:{label}']['fonts'] = page.evaluate("({body: getComputedStyle(document.body).fontFamily, h1: getComputedStyle(document.querySelector('h1')).fontFamily, fontsLoaded: document.fonts.check('16px Inter')})")
                page.goto(base, wait_until='networkidle')
                trigger = page.locator('[data-search-open]').first if name == 'hugo' else page.locator('.md-header label[for="__search"]' if mobile else '.md-search__button')
                trigger.focus()
                page.keyboard.press('Enter')
                search = page.locator('#hextra-search-dialog input') if name == 'hugo' else page.get_by_label('Search words or document ID')
                search.fill('INV-CORE-000')
                result = page.locator('#hextra-search-dialog a[href*="INV-CORE-000"]' if name == 'hugo' else '#cth-search-results a[href*="INV-CORE-000"]')
                try:
                    result.first.wait_for(timeout=5000)
                    states[f'{mode}:search_found'] = True
                except TimeoutError:
                    states[f'{mode}:search_found'] = False
                    (CACHE / f'{name}-{mode}-search.html').write_text(page.content())
                audit(f'{mode}:search')
                states[f'{mode}:search']['first_result'] = page.locator('#hextra-search-results a' if name == 'hugo' else '#cth-search-results a').first.get_attribute('href')
                page.screenshot(path=str(screenshots / f'{name}-{mode}-search.png'))
                page.keyboard.press('Escape')
                search.wait_for(state='hidden')
                states[f'{mode}:search']['escape_restores_focus'] = trigger.evaluate('el => el === document.activeElement')
                if mobile:
                    menu = page.locator('.hextra-hamburger-menu' if name == 'hugo' else '.md-header label[for="__drawer"]')
                    menu.focus()
                    page.keyboard.press('Enter')
                    states['mobile:menu_opened'] = menu.get_attribute('aria-expanded') == 'true'
                    audit('mobile:menu')
                    page.screenshot(path=str(screenshots / f'{name}-mobile-menu.png'))
                    page.keyboard.press('Escape')
                    page.wait_for_function("selector => document.querySelector(selector).getAttribute('aria-expanded') === 'false'", arg='.hextra-hamburger-menu' if name == 'hugo' else '.md-header label[for="__drawer"]')
                    states['mobile:menu_closed'] = menu.get_attribute('aria-expanded') == 'false'
                    states['mobile:menu_focus_restored'] = menu.evaluate('el => el === document.activeElement')
                context.close()
            reports[name] = {'states': states, 'external_requests': sorted(set(network)), 'javascript_errors': errors}
            server.shutdown()
            thread.join(timeout=5)
            (CACHE / 'browser-results.json').write_text(json.dumps(reports, indent=2)+'\n')
            print(name, {k: len(v['violations']) for k, v in states.items() if isinstance(v, dict) and 'violations' in v}, flush=True)
        browser.close()
    return any(
        value is False if isinstance(value, bool) else
        bool(value.get('violations') or value.get('overflow') or value.get('escape_restores_focus') is False)
        for report in reports.values() for value in report['states'].values()
    ) or any(report['javascript_errors'] for report in reports.values())


if __name__ == '__main__':
    raise SystemExit(bool(run()))
