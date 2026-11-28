#!/usr/bin/env python3
"""The schema toggle prefixes table names with their schema.

In a real headless render of Pagila, through the real toolbar button:
- off by default: a table header reads `film`, not `public.film`;
- one click shows `public.film`, lights the button, is remembered in
  localStorage, and the SVG export writes the prefixed name;
- a second click hides it again and forgets the choice;
- a page opened with ?schema=show starts with the prefix shown.

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
function entete() { return elems['public.film'].querySelector('h3').innerText.trim(); }
function memoire() { try { return localStorage.getItem('mcdview:schema'); } catch (e) { return 'x'; } }
window.addEventListener('load', function () {
  setTimeout(function () {
    var r = { depart: entete() };
    if (location.search) { r.err = window._e || 'none'; document.title = JSON.stringify(r); return; }
    var b = document.getElementById('btnSchema');
    b.click();
    r.allume = entete(); r.actif = b.classList.contains('actif'); r.memoire = memoire();
    // capture the SVG export instead of downloading it
    var blob = null, creer = URL.createObjectURL;
    URL.createObjectURL = function (x) { blob = x; return creer.call(URL, x); };
    HTMLAnchorElement.prototype.click = function () {};
    document.getElementById('exportSvg').click();
    b.click();
    r.eteint = entete(); r.memoireApres = memoire();
    blob.text().then(function (svg) {
      r.svg = svg.indexOf('>public.film<') !== -1;
      r.err = window._e || 'none';
      document.title = JSON.stringify(r);
    });
  }, 300);
});
</script>
"""


def chrome_binaire():
    for nom in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if shutil.which(nom):
            return nom
    return None


def mesurer(binaire, page, requete=''):
    sortie = subprocess.run(
        [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
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
        print('test_schema : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'pagila.html'
        subprocess.run([str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'pagila.sql'),
                        '-o', str(page), '--titre', 'Pagila'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        r, lien = mesurer(binaire, page), mesurer(binaire, page, '?schema=show')
        if r is None or lien is None:
            print(f'test_schema : FAIL — no measurement ({r!r}, {lien!r})')
            return 1
        attendu = {'depart': 'film', 'allume': 'public.film', 'actif': True, 'memoire': '1',
                   'eteint': 'film', 'memoireApres': None, 'svg': True, 'err': 'none'}
        echecs = [f'{k}: {r.get(k)!r}, expected {v!r}' for k, v in attendu.items() if r.get(k) != v]
        if lien.get('depart') != 'public.film' or lien.get('err') != 'none':
            echecs.append(f'?schema=show: header {lien.get("depart")!r}, error {lien.get("err")}')
        if echecs:
            print('test_schema : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('schéma : préfixe masqué par défaut, bouton, mémoire, export SVG, ?schema=show')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
