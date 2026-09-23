#!/usr/bin/env python3
"""The minimap's cached table layer is never stale.

dessinerMinimap() keeps the table rectangles in an offscreen canvas and only
redraws the viewport rectangle on a pan or zoom; the cache is dropped wherever
the boxes change. This checks, in a real headless render of a 40-table model
(the minimap turns on from 25 tables), that after each of: a pan, a table drag
then a pan, isolating a table, going back to the overview with Escape, and a
wheel zoom-out into compact mode, the minimap pixels equal a from-scratch
rebuild of the layer. Pointer and wheel events go through the real listeners.

Skips cleanly when no Chrome binary is available."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# 40 tables in a binary tree of FKs (t_i -> t_(i//2)): enough for the minimap,
# and every table has links, so a drag and an isolate change real geometry
FIXTURE = '\n'.join(
    ['CREATE TABLE t0 (id integer PRIMARY KEY, label text);'] +
    [f'CREATE TABLE t{i} (id integer PRIMARY KEY, parent_id integer REFERENCES t{i // 2}(id), '
     f'label text);' for i in range(1, 40)])

SONDE = r"""
<script>
window.onerror = function (m) { window._e = m; };
var ecarts = [];  // vp, plan, miniCtx… are the page's own globals
function pixels() {
  var d = miniCtx.getImageData(0, 0, miniCanvas.width, miniCanvas.height).data, h = 0;
  for (var i = 0; i < d.length; i++) h = (h * 31 + d[i]) | 0;
  return h;
}
// the current (possibly cached) minimap must equal a forced rebuild
function verifier(nom) {
  dessinerMinimap();
  var cur = pixels();
  miniCouche = null; dessinerMinimap();
  if (pixels() !== cur) ecarts.push(nom);
}
function pe(cible, type, x, y) {
  cible.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true,
    clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', button: 0 }));
  void cible.offsetLeft;
}
function pan(nom) {
  pe(vp, 'pointerdown', 10, 880);
  for (var i = 1; i <= 5; i++) pe(vp, 'pointermove', 10 + 12 * i, 880 - 7 * i);
  pe(vp, 'pointerup', 70, 845);
  verifier(nom);
}
window.addEventListener('load', function () {
  setTimeout(function () {
    vp.setPointerCapture = function () {}; vp.releasePointerCapture = function () {};
    var actif = miniCanvas.classList.contains('on');
    pan('pan');
    // drag a table (scheduled frame run synchronously), then pan
    var t = elems['public.t3'], r = t.getBoundingClientRect(), x0 = t.style.left;
    var raf = window.requestAnimationFrame;
    window.requestAnimationFrame = function (cb) { cb(performance.now()); return 0; };
    pe(t, 'pointerdown', r.left + 10, r.top + 8);
    for (var i = 1; i <= 6; i++) pe(t, 'pointermove', r.left + 10 + 30 * i, r.top + 8 + 20 * i);
    pe(t, 'pointerup', r.left + 190, r.top + 128);
    window.requestAnimationFrame = raf;
    var bouge = t.style.left !== x0;
    pan('drag puis pan');
    isoler('public.t5');
    setTimeout(function () {
      verifier('isoler');
      pan('pan en vue isolée');
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      setTimeout(function () {
        verifier('retour vue générale');
        // zoom out through the real wheel listener until compact mode kicks in
        for (var i = 0; i < 40 && !plan.classList.contains('compact'); i++)
          vp.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true,
            deltaY: 120, clientX: 500, clientY: 400 }));
        var compact = plan.classList.contains('compact');
        verifier('zoom compact');
        document.title = JSON.stringify({ err: window._e || 'none', actif: actif,
                                          bouge: bouge, compact: compact, ecarts: ecarts });
      }, 700);
    }, 700);
  }, 300);
});
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
        print('test_minimap : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        sql = Path(td) / 'arbre.sql'
        sql.write_text(FIXTURE)
        page = Path(td) / 'arbre.html'
        subprocess.run([str(RACINE / 'mcdview.py'), str(sql), '-o', str(page),
                        '--titre', 'Arbre'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        sortie = subprocess.run(
            [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--window-size=1600,900', '--virtual-time-budget=8000',
             '--dump-dom', f'file://{page}'],
            capture_output=True, text=True, timeout=60).stdout
        mt = re.search(r'<title>(.*?)</title>', sortie, re.S)
        if not mt or not mt.group(1).startswith('{'):
            print(f'test_minimap : FAIL — no measurement (title={mt and mt.group(1)!r})')
            return 1
        r = json.loads(mt.group(1))
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        if not r['actif']:
            echecs.append('minimap not active on a 40-table model (probe exercises nothing)')
        if not r['bouge']:
            echecs.append('the drag did not move the table')
        if not r['compact']:
            echecs.append('wheel zoom never reached compact mode')
        for e in r['ecarts']:
            echecs.append(f'{e}: minimap differs from a rebuilt one (stale cache)')
        if echecs:
            print('test_minimap : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('minimap : couche en cache identique à une reconstruction '
              '(pan, drag, isoler, Échap, zoom compact)')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
