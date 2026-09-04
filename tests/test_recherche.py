#!/usr/bin/env python3
"""Search suggestions list every table name before any column name.

The search input is a native <datalist>; the browser shows matching options in
document order. When a table name is shared by several tables (e.g. etablissement
/ etablissementindividu / etablissementtelephone), one table's column options
must not crowd out its sibling tables. So all table <option>s are inserted first,
then all column <option>s. This checks that ordering invariant in a real render.

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
    var opts = [].map.call(document.getElementById('noms').querySelectorAll('option'),
                           function (o) { return o.value; });
    var tkeys = {};
    D.tables.forEach(function (t) { tkeys[t.schema + '.' + t.nom] = 1; });
    var seenCol = false, tableAfterCol = 0;
    opts.forEach(function (v) {
      if (tkeys[v]) { if (seenCol) tableAfterCol++; } else { seenCol = true; }
    });
    document.title = JSON.stringify({
      err: window._e || 'none',
      opts: opts.length,
      tables: D.tables.length,
      hasCols: opts.some(function (v) { return !tkeys[v]; }),
      tableAfterCol: tableAfterCol
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
        print('test_recherche : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / 'chinook.html'
        subprocess.run(
            [str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
             '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        out = subprocess.run(
            [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--virtual-time-budget=3000', '--dump-dom', f'file://{page}'],
            capture_output=True, text=True, timeout=60).stdout
        m = re.search(r'<title>(.*?)</title>', out, re.S)
        if not m or not m.group(1).startswith('{'):
            print(f'test_recherche : FAIL — no measurement (title={m.group(1) if m else None!r})')
            return 1
        r = json.loads(m.group(1))
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        if not r['hasCols']:
            echecs.append('no column options in the datalist (colonnesEnAuto expected on this model)')
        if r['opts'] <= r['tables']:
            echecs.append(f"datalist has {r['opts']} options for {r['tables']} tables (columns missing)")
        if r['tableAfterCol'] != 0:
            echecs.append(f"{r['tableAfterCol']} table option(s) placed after a column option "
                          "(a matching table can be crowded out by another table's columns)")
        if echecs:
            print('test_recherche : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print(f"recherche : {r['tables']} table options all precede the column options "
              f"({r['opts']} total)")
    return 0


if __name__ == '__main__':
    sys.exit(principal())
