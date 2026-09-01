#!/usr/bin/env python3
"""Link routing: edges anchor to box borders, self-references draw a loop, and
highlighted edges go to the overlay above the tables.

Regression guard for the edge-anchored routing. The old routing joined box
centres, so a link started inside its own table and cut across it; a
self-reference collapsed to a zero-length (invisible) point. This checks, in a
real headless render:
  - every drawn link endpoint sits on some table's border, never at a centre;
  - a self-reference (chinook employee.reports_to) draws a real loop, not a
    zero-length path;
  - isolating a table puts its links in the #liensVif overlay (painted above the
    tables), not in the under-tables #liens layer.

Skips cleanly when no Chrome binary is available."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def chrome_binaire():
    for nom in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if shutil.which(nom):
            return nom
    return None


def titre(binaire, chemin_html):
    sortie = subprocess.run(
        [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
         '--window-size=1600,900', '--virtual-time-budget=6000',
         '--dump-dom', f'file://{chemin_html}'],
        capture_output=True, text=True, timeout=60).stdout
    m = re.search(r'<title>(.*?)</title>', sortie, re.S)
    return m.group(1) if m else ''


# runs in the page: check edge anchoring in the overview, then isolate the table
# with the self-reference and inspect the loop and the overlay
SONDE = r"""
<script>
window.onerror = function (m) { window._e = m; };
function pts(svgId) {
  return [...document.getElementById(svgId).querySelectorAll('path')].map(function (p) {
    var m = p.getAttribute('d').match(/M ([\d.-]+) ([\d.-]+) C.*?([\d.-]+) ([\d.-]+)$/);
    return m ? { sx: +m[1], sy: +m[2], ex: +m[3], ey: +m[4] } : null;
  }).filter(Boolean);
}
function boites() {
  var B = {};
  Object.keys(elems).forEach(function (c) {
    var e = elems[c];
    B[c] = { l: e.offsetLeft, t: e.offsetTop, r: e.offsetLeft + e.offsetWidth, b: e.offsetTop + e.offsetHeight,
             cx: e.offsetLeft + e.offsetWidth / 2, cy: e.offsetTop + e.offsetHeight / 2 };
  });
  return B;
}
function surBord(x, y, B) {
  for (var c in B) {
    var k = B[c], e = 1.5;
    if ((Math.abs(x - k.l) < e || Math.abs(x - k.r) < e) && y > k.t - e && y < k.b + e) return true;
    if ((Math.abs(y - k.t) < e || Math.abs(y - k.b) < e) && x > k.l - e && x < k.r + e) return true;
  }
  return false;
}
function auCentre(x, y, B) {
  for (var c in B) if (Math.abs(x - B[c].cx) < 2 && Math.abs(y - B[c].cy) < 2) return true;
  return false;
}
window.addEventListener('load', function () {
  setTimeout(function () {
    var B = boites();
    var horsBord = 0, centres = 0;
    pts('liens').forEach(function (p) {
      if (!surBord(p.sx, p.sy, B)) horsBord++;
      if (!surBord(p.ex, p.ey, B)) horsBord++;
      if (auCentre(p.sx, p.sy, B) || auCentre(p.ex, p.ey, B)) centres++;
    });
    // now isolate the self-referencing table and look at the overlay + the loop
    isoler('public.employee');
    setTimeout(function () {
      var vif = pts('liensVif');
      var sousTable = pts('liens').length;
      var boucle = vif.filter(function (p) {
        return Math.abs(p.sx - p.ex) > 1 || Math.abs(p.sy - p.ey) > 1;  // not a zero-length point
      });
      document.title = JSON.stringify({
        err: window._e || 'none', horsBord: horsBord, centres: centres,
        vif: vif.length, sousTable: sousTable, boucles: boucle.length
      });
    }, 700);
  }, 300);
});
</script>
"""


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_liens : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'chinook.html'
        subprocess.run(
            [str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
             '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        t = titre(binaire, str(page))
        if not t.startswith('{'):
            print(f'test_liens : FAIL — no measurement (title={t!r})')
            return 1
        r = json.loads(t)
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        if r['horsBord']:
            echecs.append(f"{r['horsBord']} link endpoint(s) not on a box border (edge anchoring broken)")
        if r['centres']:
            echecs.append(f"{r['centres']} link endpoint(s) at a box centre (old center-to-center routing)")
        if r['vif'] < 1:
            echecs.append('isolating a table put no links in the #liensVif overlay')
        if r['sousTable'] != 0:
            echecs.append(f"{r['sousTable']} focused-view link(s) left in the under-tables layer instead of the overlay")
        if r['boucles'] < 1:
            echecs.append('the self-reference (employee.reports_to) drew no visible loop')
        if echecs:
            print('test_liens : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print(f"liens : edges on borders, self-loop drawn, {r['vif']} highlighted links raised to the overlay")
    return 0


if __name__ == '__main__':
    sys.exit(principal())
