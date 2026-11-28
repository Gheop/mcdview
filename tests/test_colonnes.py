#!/usr/bin/env python3
"""Hovering a link or a key column lights the paired key columns.

In a real headless render on Chinook, through the real mouseover listener:
- hovering the hit path of the track.album_id -> album.album_id link lights
  album_id in both tables, and nothing else;
- hovering the FK column track.genre_id lights it and genre.genre_id;
- hovering the referenced column track.track_id lights every FK column that
  points at it (invoice_line.track_id, playlist_track.track_id);
- hovering a plain column (track.name) lights nothing;
- leaving the plan clears every highlight.

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
function vifs() {
  return [].slice.call(document.querySelectorAll('.table li.colvif')).map(function (li) {
    return li.closest('.table').dataset.cle + '.' + li.dataset.col;
  }).sort();
}
function survolCol(cle, col) {
  var li = [].slice.call(elems[cle].querySelectorAll('li')).filter(function (l) {
    return l.dataset.col === col; })[0];
  li.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
}
window.addEventListener('load', function () {
  setTimeout(function () {
    var r = {};
    var i = liensVus.findIndex(function (f) { return f.de === 'public.track' && f.col === 'album_id'; });
    document.querySelector('#liensClic path[data-fk="' + i + '"]')
      .dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    r.lien = vifs();
    survolCol('public.track', 'genre_id'); r.fk = vifs();
    survolCol('public.track', 'track_id'); r.pk = vifs();
    survolCol('public.track', 'name'); r.simple = vifs();
    survolCol('public.track', 'genre_id');
    document.getElementById('plan').dispatchEvent(new MouseEvent('mouseleave'));
    r.sortie = vifs();
    r.err = window._e || 'none';
    document.title = JSON.stringify(r);
  }, 300);
});
</script>
"""

ATTENDU = {
    'lien': ['public.album.album_id', 'public.track.album_id'],
    'fk': ['public.genre.genre_id', 'public.track.genre_id'],
    'pk': ['public.invoice_line.track_id', 'public.playlist_track.track_id', 'public.track.track_id'],
    'simple': [],
    'sortie': [],
}


def chrome_binaire():
    for nom in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if shutil.which(nom):
            return nom
    return None


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_colonnes : skipped (no Chrome binary found)')
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
            print(f'test_colonnes : FAIL — no measurement (title={mt and mt.group(1)!r})')
            return 1
        r = json.loads(mt.group(1))
        echecs = [f"JS error: {r['err']}"] if r['err'] != 'none' else []
        for cas, attendu in ATTENDU.items():
            if r[cas] != attendu:
                echecs.append(f'{cas}: lit {r[cas]}, expected {attendu}')
        if echecs:
            print('test_colonnes : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('colonnes clés : survol d\'un lien, d\'une FK, d\'une PK référencée, sortie')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
