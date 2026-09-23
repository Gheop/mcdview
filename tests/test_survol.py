#!/usr/bin/env python3
"""Hovering a table updates the link layers incrementally, with the exact result
of a full redraw.

A hover only changes which links are highlighted, so survoler() moves the paths
of the old and new hovered tables between #liens and #liensVif instead of
rewriting every path. This checks, in a real headless render on Chinook (a
self-reference, several hubs), that after a series of hovers through the real
mouseover listener — then a mouseleave — the two layers hold the same links
(same geometry, same classes, same layer) as a from-scratch dessinerLiens() on
the same state. With cardinalities shown, the full redraw path must still run.

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
// canonical view of the two layers: one "layer|sorted classes|d" per link path
function etat() {
  var out = [];
  ['liens', 'liensVif'].forEach(function (id) {
    [].slice.call(document.getElementById(id).querySelectorAll('path.lien')).forEach(function (p) {
      out.push(id + '|' + [].slice.call(p.classList).sort().join(' ') + '|' + p.getAttribute('d'));
    });
  });
  return out.sort().join('\n');
}
function survol(cle) { elems[cle].dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); }
window.addEventListener('load', function () {
  setTimeout(function () {
    var ecarts = [];
    ['public.employee', 'public.track', 'public.invoice', 'public.customer'].forEach(function (cle) {
      survol(cle);
      var inc = etat(); dessinerLiens(); var ref = etat();
      if (inc !== ref) ecarts.push('hover ' + cle);
    });
    document.getElementById('plan').dispatchEvent(new MouseEvent('mouseleave'));
    var inc = etat(); dessinerLiens();
    if (inc !== etat()) ecarts.push('mouseleave');
    var vifApres = document.getElementById('liensVif').querySelectorAll('path.lien').length;
    // cardinalities on: markers must follow the hover (full redraw fallback)
    document.getElementById('btnCard').click();
    survol('public.track');
    var marquesVives = document.querySelectorAll('#liensVif .marque.vif').length;
    document.title = JSON.stringify({ err: window._e || 'none', ecarts: ecarts,
                                      vifApres: vifApres, marquesVives: marquesVives });
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
        if r['marquesVives'] < 1:
            echecs.append('with cardinalities on, hovering did not highlight the markers')
        if echecs:
            print('test_survol : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('survol : mise à jour incrémentale identique au redessin complet (4 survols + sortie)')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
