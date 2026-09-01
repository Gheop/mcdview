#!/usr/bin/env python3
"""Layout undo: a moved table can be put back with Ctrl+Z / the undo button.

Regression guard for the undo stack. It drives the real user path in a headless
render: drag a table in the overview (pointer events), then press Ctrl+Z, and
check the table returns to where it was and the undo button hides again. The
drag and the keydown go through the same handlers a viewer triggers.

Skips cleanly when no Chrome binary is available."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# runs in the page: stub pointer capture (synthetic pointers have no real
# capture), drag the first table by a screen delta, then undo with Ctrl+Z
SONDE = r"""
<script>
window.onerror = function (m) { window._e = m; };
window.addEventListener('load', function () {
  setTimeout(function () {
    var vp = document.getElementById('viewport');
    vp.setPointerCapture = function () {}; vp.releasePointerCapture = function () {};
    var cle = Object.keys(elems).find(function (c) { return !elems[c].classList.contains('efface'); });
    var el = elems[cle];
    // read the committed target position (el.style), not offsetLeft: the undo
    // glides the box back over the CSS transition, which virtual time freezes
    function pos() { return [parseInt(el.style.left, 10), parseInt(el.style.top, 10)]; }
    var depart = pos();
    var r = el.getBoundingClientRect();
    var x = r.left + r.width / 2, y = r.top + r.height / 2;
    function pev(type, cx, cy) {
      el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true,
        clientX: cx, clientY: cy, pointerId: 1, pointerType: 'mouse', button: 0 }));
    }
    pev('pointerdown', x, y);
    pev('pointermove', x + 80, y + 60);   // > 3px: a real move
    void el.offsetLeft;                    // flush layout between synthetic events
    pev('pointermove', x + 80, y + 60);
    pev('pointerup', x + 80, y + 60);
    var apres = pos();
    var boutonApresDrag = document.getElementById('annuler').hidden === false;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true }));
    var restaure = pos();
    var boutonApresUndo = document.getElementById('annuler').hidden === true;
    document.title = JSON.stringify({
      err: window._e || 'none',
      bougé: apres[0] !== depart[0] || apres[1] !== depart[1],
      boutonApresDrag: boutonApresDrag,
      restauré: restaure[0] === depart[0] && restaure[1] === depart[1],
      boutonApresUndo: boutonApresUndo
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


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_undo : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'chinook.html'
        subprocess.run(
            [str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
             '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        out = subprocess.run(
            [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--window-size=1600,900', '--virtual-time-budget=3000',
             '--dump-dom', f'file://{page}'],
            capture_output=True, text=True, timeout=60).stdout
        m = re.search(r'<title>(.*?)</title>', out, re.S)
        if not m or not m.group(1).startswith('{'):
            print(f'test_undo : FAIL — no measurement (title={m.group(1) if m else None!r})')
            return 1
        r = json.loads(m.group(1))
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        if not r['bougé']:
            echecs.append('dragging a table did not move it (test setup)')
        if not r['boutonApresDrag']:
            echecs.append('the undo button stayed hidden after a move')
        if not r['restauré']:
            echecs.append('Ctrl+Z did not put the table back where it was')
        if not r['boutonApresUndo']:
            echecs.append('the undo button stayed visible after the stack emptied')
        if echecs:
            print('test_undo : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('undo : a dragged table returns on Ctrl+Z, the button tracks the stack')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
