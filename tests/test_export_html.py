#!/usr/bin/env python3
"""Export HTML with the current layout: the "HTML (with layout)" menu item
downloads a self-contained copy of the page with the dragged positions baked
into the `const D` island — not a dump of the rendered DOM.

Checks, in a headless render: the export bakes the current overview positions,
it is a pristine template (no rendered .table nodes → no bloat), and the data
island keeps its no-raw-"<" security invariant.

Skips cleanly when no Chrome binary is available."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# runs in the page: move a table's home position, export, and inspect the copy
# by parsing it (DOMParser), never by string-matching (the probe's own text
# would be cloned into the export and skew a substring count)
SONDE = r"""
<script>
window.onerror = function (m) { window._e = m; };
window.addEventListener('load', function () {
  setTimeout(function () {
    var cap = null;
    URL.createObjectURL = function (b) { cap = b; return 'blob:x'; };
    HTMLAnchorElement.prototype.click = function () {};
    var cle = Object.keys(elems)[0];
    origines[cle] = { x: origines[cle].x + 500, y: origines[cle].y + 300 };
    var attendu = origines[cle];
    exporterHTML();
    var rd = new FileReader();
    rd.onload = function () {
      var s = rd.result;
      var doc = new DOMParser().parseFromString(s, 'text/html');
      var island = (s.match(/const D = (.*);/) || [])[1] || '';
      var d = JSON.parse(island.replace(/\\u003c/g, '<'));
      var t = d.tables.find(function (x) { return (x.schema + '.' + x.nom) === cle; });
      document.title = JSON.stringify({
        err: window._e || 'none',
        doctype: s.slice(0, 15).toLowerCase().indexOf('<!doctype html') === 0,
        baked: t && t.x === attendu.x && t.y === attendu.y,
        tablesRendues: doc.querySelectorAll('#plan .table').length,
        liensRendus: doc.querySelectorAll('#plan #liens path').length,
        svgLiens: doc.querySelectorAll('#plan #liens').length,
        islandRawLt: island.indexOf('<') >= 0,
        octets: s.length
      });
    };
    rd.readAsText(cap);
  }, 400);
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
        print('test_export_html : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'chinook.html'
        subprocess.run(
            [str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
             '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        octets_origine = len(page.read_text())
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        out = subprocess.run(
            [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--window-size=1600,900', '--virtual-time-budget=3000',
             '--dump-dom', f'file://{page}'],
            capture_output=True, text=True, timeout=60).stdout
        m = re.search(r'<title>(.*?)</title>', out, re.S)
        if not m or not m.group(1).startswith('{'):
            print(f'test_export_html : FAIL — no measurement (title={m.group(1) if m else None!r})')
            return 1
        r = json.loads(m.group(1))
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        if not r['doctype']:
            echecs.append('export does not start with <!doctype html>')
        if not r['baked']:
            echecs.append('the current position was not baked into the exported island')
        if r['tablesRendues'] != 0:
            echecs.append(f"{r['tablesRendues']} rendered .table node(s) in the export (bloat / not a clean template)")
        if r['liensRendus'] != 0:
            echecs.append(f"{r['liensRendus']} rendered link path(s) left in the export")
        if r['svgLiens'] != 1:
            echecs.append(f"#plan should hold exactly one empty #liens svg, found {r['svgLiens']}")
        if r['islandRawLt']:
            echecs.append('a raw "<" leaked into the const D island (XSS invariant broken)')
        if r['octets'] > octets_origine * 1.5:
            echecs.append(f"export is {r['octets']} bytes vs {octets_origine} generated (bloated)")
        if echecs:
            print('test_export_html : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print(f"export HTML : layout baked, clean template, island safe "
              f"({r['octets']} bytes vs {octets_origine} generated)")
    return 0


if __name__ == '__main__':
    sys.exit(principal())
