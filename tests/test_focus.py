#!/usr/bin/env python3
"""Focus at a chosen degree, on one table or several.

In a real headless render of Pagila, through real pointer events (the
pointerdown/pointerup path, with modifier keys) and the real degree buttons:
- a plain click isolates film with its direct neighbours (#public.film);
- degree 2 keeps every table two relations away, laid out with no two boxes
  overlapping, and the permalink carries it (#public.film;2);
- a Ctrl+click on a kept table adds it as a second root;
- Escape goes back to the overview and drops roots, degree and permalink;
- in the overview, Ctrl+click marks country and language, and a plain click
  on one of them isolates both together with their neighbours;
- a page opened on #public.country+public.language;2 restores that focus,
  an old #public.film permalink still opens the star, and an unknown key or
  an out-of-range degree is ignored or clamped.
Expected sets come from the parsed FK graph, not from the page.

Skips cleanly when no Chrome binary is available."""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

SONDE = r"""
<style>*{transition:none!important}</style>
<script>
window.onerror = function (m) { window._e = m; };
function gardes() {
  return Object.keys(elems).filter(function (c) { return !elems[c].classList.contains('efface'); }).sort();
}
function chevauche() {  // any two kept boxes overlapping?
  var g = gardes(), b = g.map(function (c) { var e = elems[c];
    return [parseFloat(e.style.left), parseFloat(e.style.top), e.offsetWidth, e.offsetHeight]; });
  for (var i = 0; i < b.length; i++) for (var j = i + 1; j < b.length; j++) {
    var A = b[i], B = b[j];
    if (A[0] < B[0] + B[2] && B[0] < A[0] + A[2] && A[1] < B[1] + B[3] && B[1] < A[1] + A[3])
      return g[i] + ' / ' + g[j];
  }
  return '';
}
function etat() {
  return { gardes: gardes(), hash: decodeURIComponent(location.hash), racines: racines.slice().sort(),
           degres: !document.getElementById('degres').hidden, chevauche: chevauche() };
}
function clic(cle, mods) {
  var t = elems[cle], r = t.getBoundingClientRect(), vp = document.getElementById('viewport');
  vp.setPointerCapture = function () {}; vp.releasePointerCapture = function () {};
  var x = r.left + Math.min(30, r.width / 2), y = r.top + r.height / 2;
  var sous = document.elementFromPoint(x, y);
  if (!sous || sous.closest('.table') !== t) { window._e = 'table hidden under the pointer: ' + cle + ' at ' + Math.round(x) + ',' + Math.round(y) + ' by ' + (sous ? (sous.id || sous.className || sous.tagName) + ' in ' + ((sous.closest('[id]') || {}).id) : 'nothing'); return; }
  ['pointerdown', 'pointerup'].forEach(function (type) {
    var o = { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 1,
              pointerType: 'mouse', button: 0 };
    for (var k in (mods || {})) o[k] = mods[k];
    t.dispatchEvent(new PointerEvent(type, o));
  });
}
var etapes = [], r = {};
function suite(f) { etapes.push(f); }
function lancer() {
  var f = etapes.shift();
  if (!f) { r.err = window._e || 'none'; document.title = JSON.stringify(r); return; }
  f(); setTimeout(lancer, 700);
}
if (location.hash) {
  suite(function () { r.lien = etat(); });
} else {
  suite(function () { clic('public.film'); });
  suite(function () { r.simple = etat(); document.querySelector('#degres button[data-degre="2"]').click(); });
  suite(function () { r.degre2 = etat(); clic('public.store', { ctrlKey: true }); });
  suite(function () { r.deux = etat();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); });
  suite(function () { r.general = etat(); clic('public.country', { ctrlKey: true }); });
  suite(function () { clic('public.language', { metaKey: true }); });
  suite(function () { r.marquees = document.querySelectorAll('.table.marquee').length; clic('public.country'); });
  suite(function () { r.ensemble = etat(); });
}
window.addEventListener('load', function () { setTimeout(lancer, 400); });
</script>
"""


def chrome_binaire():
    for nom in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if shutil.which(nom):
            return nom
    return None


def mesurer(binaire, page, ancre=''):
    sortie = subprocess.run(
        [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
         '--window-size=1600,900', '--virtual-time-budget=15000',
         '--dump-dom', f'file://{page}{ancre}'],
        capture_output=True, text=True, timeout=90).stdout
    mt = re.search(r'<title>(.*?)</title>', sortie, re.S)
    if not mt or not mt.group(1).startswith('{'):
        return None
    return json.loads(mt.group(1))


def autour(adj, racines, degre):
    vus, front = set(racines), list(racines)
    for _ in range(degre):
        front = [v for c in front for v in adj.get(c, ()) if v not in vus and not vus.add(v)]
    return sorted(vus)


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_focus : skipped (no Chrome binary found)')
        return 0
    spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
    mcdview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcdview)
    _, fks, _ = mcdview.analyser(str(RACINE / 'exemples' / 'pagila.sql'))
    adj = {}
    for f in fks:
        adj.setdefault(f['de'], set()).add(f['vers'])
        adj.setdefault(f['vers'], set()).add(f['de'])
    tout = sorted(set(adj) | {f['de'] for f in fks})
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'pagila.html'
        subprocess.run([str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'pagila.sql'),
                        '-o', str(page), '--titre', 'Pagila'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        r = mesurer(binaire, page)
        liens = {a: mesurer(binaire, page, a) for a in (
            '#public.country+public.language;2', '#public.film', '#public.nope+public.film;9')}
        if r is None or None in liens.values():
            print(f'test_focus : FAIL — no measurement ({r!r}, {liens!r})')
            return 1
        echecs = [f"JS error: {r['err']}"] if r['err'] != 'none' else []

        def verifier(nom, e, racines, degre, ancre):
            if e is None:
                echecs.append(f'{nom}: missing')
                return
            attendu = autour(adj, racines, degre)
            if e['gardes'] != attendu:
                echecs.append(f"{nom}: kept {e['gardes']}, expected {attendu}")
            if e['racines'] != sorted(racines):
                echecs.append(f"{nom}: roots {e['racines']}, expected {sorted(racines)}")
            if e['hash'] != ancre:
                echecs.append(f"{nom}: permalink {e['hash']!r}, expected {ancre!r}")
            if e['chevauche']:
                echecs.append(f"{nom}: overlapping boxes {e['chevauche']}")
            if not e['degres']:
                echecs.append(f'{nom}: degree control hidden during a focus')

        verifier('click', r.get('simple'), ['public.film'], 1, '#public.film')
        verifier('degree 2', r.get('degre2'), ['public.film'], 2, '#public.film;2')
        verifier('ctrl+click', r.get('deux'), ['public.film', 'public.store'], 2,
                 '#public.film+public.store;2')
        g = r.get('general') or {}
        if g.get('gardes') != tout or g.get('hash') or g.get('racines') or g.get('degres'):
            echecs.append(f'escape: overview not restored ({g})')
        if r.get('marquees') != 2:
            echecs.append(f"overview ctrl/cmd+click marked {r.get('marquees')} tables, expected 2")
        verifier('marked together', r.get('ensemble'), ['public.country', 'public.language'], 1,
                 '#public.country+public.language')
        verifier('permalink a+b;2', liens['#public.country+public.language;2']['lien'],
                 ['public.country', 'public.language'], 2, '#public.country+public.language;2')
        verifier('old permalink', liens['#public.film']['lien'], ['public.film'], 1, '#public.film')
        verifier('bad permalink', liens['#public.nope+public.film;9']['lien'], ['public.film'], 3,
                 '#public.film;3')
        for a, e in liens.items():
            if e['err'] != 'none':
                echecs.append(f"{a}: JS error {e['err']}")
        if echecs:
            print('test_focus : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('focus : degré 1-3, plusieurs racines (Ctrl/⌘+clic), marques en vue générale, '
              'liens permanents, aucun chevauchement')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
