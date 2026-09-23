#!/usr/bin/env python3
"""Hovering or dragging a table updates the link layers incrementally, with the
exact result of a full redraw.

A hover only changes which links are highlighted, so survoler() moves the paths
of the old and new hovered tables between #liens and #liensVif; a drag only
moves one box, so majLiensDe() reroutes that table's links alone. This checks,
in a real headless render on Chinook (a self-reference, several hubs), that
after hovers through the real mouseover listener, a mouseleave, and a drag
through the real pointer events, the three layers (normal, highlighted, hit
paths) hold the same links — same index, geometry, classes, layer — as a
from-scratch dessinerLiens() on the same state. With cardinalities shown, the
full redraw path must still run.

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
// canonical view of the three layers: one "layer|index|sorted classes|d" per path
function etat() {
  var out = [];
  ['liens', 'liensVif', 'liensClic'].forEach(function (id) {
    [].slice.call(document.getElementById(id).querySelectorAll('path')).forEach(function (p) {
      out.push(id + '|' + p.getAttribute('data-fk') + '|' +
               [].slice.call(p.classList).sort().join(' ') + '|' + p.getAttribute('d'));
    });
  });
  return out.sort().join('\n');
}
function survol(cle) { elems[cle].dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); }
window.addEventListener('load', function () {
  setTimeout(function () {
    var ecarts = window._ecarts = [];
    ['public.employee', 'public.track', 'public.invoice', 'public.customer'].forEach(function (cle) {
      survol(cle);
      var inc = etat(); dessinerLiens(); var ref = etat();
      if (inc !== ref) ecarts.push('hover ' + cle);
    });
    document.getElementById('plan').dispatchEvent(new MouseEvent('mouseleave'));
    var inc = etat(); dessinerLiens();
    if (inc !== etat()) ecarts.push('mouseleave');
    var vifApres = document.getElementById('liensVif').querySelectorAll('path.lien').length;
    // drag a hub table through the real pointer path, let the frame run, compare
    // same recipe as test_undo: a synthetic pointer cannot be captured, events
    // bubble from the table, layout is flushed between them, and the position is
    // read from style (virtual time freezes CSS transitions, offsetLeft lags)
    var t = elems['public.track'], r = t.getBoundingClientRect(), vp = document.getElementById('viewport');
    vp.setPointerCapture = function () {}; vp.releasePointerCapture = function () {};
    var px = r.left + 20, py = r.top + 10, x0 = t.style.left;
    function ev(type) { t.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true,
      clientX: px, clientY: py, pointerId: 1, pointerType: 'mouse', button: 0 })); void t.offsetLeft; }
    // the drag schedules its link update with requestAnimationFrame; whether a
    // frame runs before a timer under virtual time is racy, so run the scheduled
    // callback synchronously (same code path, deterministic)
    var raf = window.requestAnimationFrame;
    window.requestAnimationFrame = function (cb) { cb(performance.now()); return 0; };
    ev('pointerdown');
    for (var i = 0; i < 6; i++) { px += 25; py += 15; ev('pointermove'); }
    ev('pointerup');
    window.requestAnimationFrame = raf;
    var inc = etat(); dessinerLiens();
    if (inc !== etat()) ecarts.push('drag public.track');
    finir(vifApres, t.style.left !== x0);  // the drag really moved the table
  }, 300);
});
function finir(vifApres, bouge) {
    var ecarts = window._ecarts;
    // cardinalities on: markers must follow the hover (full redraw fallback)
    document.getElementById('btnCard').click();
    survol('public.track');
    var marquesVives = document.querySelectorAll('#liensVif .marque.vif').length;
    document.title = JSON.stringify({ err: window._e || 'none', ecarts: ecarts, bouge: bouge,
                                      vifApres: vifApres, marquesVives: marquesVives });
}
</script>
"""


def chrome_binaire():
    for nom in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if shutil.which(nom):
            return nom
    return None


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_survol : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'chinook.html'
        subprocess.run([str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
                        '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        sortie = subprocess.run(
            [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--window-size=1600,900', '--virtual-time-budget=6000',
             '--dump-dom', f'file://{page}'],
            capture_output=True, text=True, timeout=60).stdout
        mt = re.search(r'<title>(.*?)</title>', sortie, re.S)
        if not mt or not mt.group(1).startswith('{'):
            print(f'test_survol : FAIL — no measurement (title={mt and mt.group(1)!r})')
            return 1
        r = json.loads(mt.group(1))
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        for e in r['ecarts']:
            echecs.append(f'{e}: incremental layers differ from a full redraw')
        if r['vifApres'] != 0:
            echecs.append(f"{r['vifApres']} link(s) still highlighted after mouseleave")
        if not r['bouge']:
            echecs.append('the drag did not move the table (probe did not exercise it)')
        if r['marquesVives'] < 1:
            echecs.append('with cardinalities on, hovering did not highlight the markers')
        if echecs:
            print('test_survol : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('survol/drag : mise à jour incrémentale identique au redessin complet '
              '(4 survols, sortie, drag)')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
