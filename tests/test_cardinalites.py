#!/usr/bin/env python3
"""Cardinality markers: off by default, toggled by the toolbar button, blue with
a short label on the hovered/isolated table's links.

Checks, in a real headless render: no crow's-foot markers until the toggle is
pressed; markers appear after it; isolating a table draws the vif (blue) markers
plus the short cardinality labels on its links.

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
window.addEventListener('load', function () {
  setTimeout(function () {
    function markup() { return svg.innerHTML + svgVif.innerHTML; }
    var avantToggle = /class="marque/.test(markup());
    document.getElementById('btnCard').click();
    var apresToggle = (markup().match(/class="marque/g) || []).length;
    var actif = document.getElementById('btnCard').classList.contains('actif');
    isoler('public.invoice');
    setTimeout(function () {
      var vh = svgVif.innerHTML;
      document.title = JSON.stringify({
        err: window._e || 'none',
        avantToggle: avantToggle,
        apresToggle: apresToggle,
        actif: actif,
        vifMark: /class="marque vif"/.test(vh),
        label: /class="cardtxt"/.test(vh)
      });
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
        print('test_cardinalites : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'chinook.html'
        subprocess.run(
            [str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
             '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        out = subprocess.run(
            [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--window-size=1600,900', '--virtual-time-budget=4000',
             '--dump-dom', f'file://{page}'],
            capture_output=True, text=True, timeout=60).stdout
        m = re.search(r'<title>(.*?)</title>', out, re.S)
        if not m or not m.group(1).startswith('{'):
            print(f'test_cardinalites : FAIL — no measurement (title={m.group(1) if m else None!r})')
            return 1
        r = json.loads(m.group(1))
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        if r['avantToggle']:
            echecs.append('markers present before the toggle (should be off by default)')
        if r['apresToggle'] <= 0:
            echecs.append('no markers after pressing the toggle')
        if not r['actif']:
            echecs.append('the toggle button did not become active')
        if not r['vifMark']:
            echecs.append('isolating a table drew no blue (vif) markers on its links')
        if not r['label']:
            echecs.append('isolating a table showed no cardinality label')
        if echecs:
            print('test_cardinalites : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print(f"cardinalites : off by default, {r['apresToggle']} markers on toggle, "
              "blue markers + labels on the isolated table")
    return 0


if __name__ == '__main__':
    sys.exit(principal())
