#!/usr/bin/env python3
"""Light and dark themes from one light-dark() palette.

In a real headless render of a 30-table model (so the minimap is on), for a
light system, a dark system (--blink-settings=preferredColorScheme), and the
?theme=dark deep-link, then after a click on the theme toggle:
- the page background is the palette's light or dark side;
- color-scheme follows the toggle, so the search field and scrollbars do too
  (before light-dark(), the toggle left them on the system's scheme);
- the --credit stamp ink follows the toggle (it used to follow the system only);
- the minimap frame is stroked with the resolved accent colour, not with the
  light-dark(…) text a canvas refuses;
- the same holds with the @supports fallback palettes forced, as a browser
  without light-dark() would apply them.

Skips cleanly when no Chrome binary is available."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

SONDE = r"""
<script>
window.onerror = function (m) { window._e = m; };
function etat() {
  dessinerMinimap();
  var tampon = document.querySelector('#credit > a, #credit > span');
  return { fond: getComputedStyle(document.body).backgroundColor,
           schema: getComputedStyle(document.getElementById('cherche')).colorScheme,
           themeRacine: getComputedStyle(document.documentElement).colorScheme,
           tampon: tampon ? getComputedStyle(tampon).color : 'absent',
           cadre: miniCtx.strokeStyle };
}
window.addEventListener('load', function () {
  setTimeout(function () {
    var r = { avant: etat() };
    document.getElementById('theme').click();
    r.apres = etat();
    r.err = window._e || 'none';
    document.title = JSON.stringify(r);
  }, 300);
});
</script>
"""

CLAIR = {'fond': 'rgb(244, 244, 246)', 'tampon': 'rgb(192, 38, 27)', 'cadre': '#0b74c4'}
SOMBRE = {'fond': 'rgb(30, 33, 38)', 'tampon': 'rgb(229, 103, 92)', 'cadre': '#4aa8e8'}


def chrome_binaire():
    for nom in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if shutil.which(nom):
            return nom
    return None


def mesurer(binaire, page, requete='', sombre=False):
    options = ['--blink-settings=preferredColorScheme=0'] if sombre else []
    sortie = subprocess.run(
        [binaire, '--headless=new', '--disable-gpu', '--no-sandbox', *options,
         '--window-size=1600,900', '--virtual-time-budget=6000',
         '--dump-dom', f'file://{page}{requete}'],
        capture_output=True, text=True, timeout=60).stdout
    mt = re.search(r'<title>(.*?)</title>', sortie, re.S)
    if not mt or not mt.group(1).startswith('{'):
        return None
    return json.loads(mt.group(1))


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_theme : skipped (no Chrome binary found)')
        return 0
    ddl = '\n'.join(f'CREATE TABLE t{i} (\n  id integer PRIMARY KEY,\n'
                    f'  p_id integer REFERENCES t{max(i - 1, 0)} (id)\n);' for i in range(30))
    with tempfile.TemporaryDirectory() as td:
        sql, page = Path(td) / 'trente.sql', Path(td) / 'trente.html'
        sql.write_text(ddl)
        subprocess.run([str(RACINE / 'mcdview.py'), str(sql), '-o', str(page)],
                       check=True, capture_output=True)
        html = page.read_text().replace('</body>', SONDE + '</body>')
        page.write_text(html)
        # a browser without light-dark() takes the @supports fallback: force
        # its condition true, so its palettes override the light-dark() ones
        # as they would there
        garde = '@supports not (color: light-dark(#000, #fff))'
        echecs = [] if garde in html else [f'fallback guard {garde!r} not found in the page']
        repli = Path(td) / 'repli.html'
        repli.write_text(html.replace(garde, '@supports (color: red)'))
        # (case, measurement, expected before the click, expected after it):
        # the toggle cycles system -> light -> dark, skipping a state that
        # looks like the current one
        cas = [('light system', mesurer(binaire, page), CLAIR, SOMBRE, 'dark'),
               ('dark system', mesurer(binaire, page, sombre=True), SOMBRE, CLAIR, 'light'),
               ('?theme=dark', mesurer(binaire, page, '?theme=dark'), SOMBRE, None, None),
               ('fallback, light system', mesurer(binaire, repli), CLAIR, SOMBRE, 'dark'),
               ('fallback, dark system', mesurer(binaire, repli, sombre=True), SOMBRE, CLAIR, 'light')]
        for nom, r, avant, apres, schema_apres in cas:
            if r is None:
                echecs.append(f'{nom}: no measurement')
                continue
            if r['err'] != 'none':
                echecs.append(f"{nom}: JS error {r['err']}")
            for cle, v in avant.items():
                if r['avant'][cle] != v:
                    echecs.append(f"{nom}: {cle} {r['avant'][cle]!r}, expected {v!r}")
            if apres:
                for cle, v in apres.items():
                    if r['apres'][cle] != v:
                        echecs.append(f"{nom}, after the toggle: {cle} {r['apres'][cle]!r}, expected {v!r}")
                if r['apres']['schema'] != schema_apres or r['apres']['themeRacine'] != schema_apres:
                    echecs.append(f"{nom}, after the toggle: color-scheme {r['apres']['schema']!r} "
                                  f"(root {r['apres']['themeRacine']!r}), expected {schema_apres!r}")
        if echecs:
            print('test_theme : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('thème : palette light-dark() et repli @supports, bascule, color-scheme des champs, '
              'tampon, minimap')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
