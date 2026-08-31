#!/usr/bin/env python3
"""Saved-position restore must not animate the tables.

Regression guard for the "links point into space on open" bug: dragged/
rearranged positions are remembered per model in localStorage and re-applied on
load. If that re-application changes each box's left/top after the layout has
settled at the auto-placement spot, the .table left/top CSS transition animates
the boxes from placement to their saved spot; the first links are drawn against
the moving boxes and point into empty space until a later redraw.

The check is deterministic under Chrome's virtual time (which freezes CSS
transitions near their start): seed saved positions offset by a known delta,
reload, and read each box's rendered offsetLeft/offsetTop. A box that is
animating is frozen at the auto-placement spot, so offsetLeft differs from the
saved position; a box restored instantly sits exactly on it. Every box must sit
exactly on its saved position.

Skips cleanly when no Chrome binary is available (e.g. a runner without one)."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DELTA_X, DELTA_Y = 400, 250  # how far the seeded positions sit from placement


def chrome_binaire():
    for nom in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if shutil.which(nom):
            return nom
    return None


def titre_apres_chargement(binaire, profil, chemin_html):
    """Load the page in headless Chrome and return its <title> once the inline
    script has rewritten it (virtual time lets the load handler run)."""
    sortie = subprocess.run(
        [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
         f'--user-data-dir={profil}', '--window-size=1600,900',
         '--virtual-time-budget=3000', '--dump-dom', f'file://{chemin_html}'],
        capture_output=True, text=True, timeout=60).stdout
    m = re.search(r'<title>(.*?)</title>', sortie, re.S)
    return m.group(1) if m else ''


def page_avec_script(html_source, script, chemin):
    Path(chemin).write_text(html_source.replace('</body>', script + '</body>'))


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_positions : skipped (no Chrome binary found)')
        return 0

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        page = td / 'chinook.html'
        subprocess.run(
            [str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
             '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        source = page.read_text()
        profil = td / 'profil'

        # phase 1: shift every table off its placement spot and persist that
        seed = td / 'seed.html'
        page_avec_script(source,
            "<script>window.addEventListener('load',function(){"
            "Object.keys(elems).forEach(function(c){var o=origines[c];"
            f"origines[c]={{x:o.x+{DELTA_X},y:o.y+{DELTA_Y}}};}});"
            "sauverPositions();document.title='SEEDED';"
            "});</script>", seed)
        if titre_apres_chargement(binaire, str(profil), str(seed)) != 'SEEDED':
            print('test_positions : FAIL — could not seed saved positions')
            return 1

        # phase 2: reload the real page (same profile → localStorage) and report,
        # for each table, how far its rendered box sits from its saved position
        check = td / 'check.html'
        page_avec_script(source,
            "<script>window.addEventListener('load',function(){"
            "var d=Object.keys(elems).map(function(c){"
            "return [c,elems[c].offsetLeft-origines[c].x,elems[c].offsetTop-origines[c].y];});"
            "document.title='DELTAS'+JSON.stringify(d);"
            "});</script>", check)
        titre = titre_apres_chargement(binaire, str(profil), str(check))
        if not titre.startswith('DELTAS'):
            print(f'test_positions : FAIL — no measurement (title={titre!r})')
            return 1

        deltas = json.loads(titre[len('DELTAS'):])
        deviants = [(c, dx, dy) for c, dx, dy in deltas if dx or dy]
        if deviants:
            print('test_positions : FAIL — boxes not on their saved positions '
                  '(restore animated instead of jumping):')
            for c, dx, dy in deviants[:5]:
                print(f'  {c}: off by ({dx}, {dy}) px from the saved spot')
            return 1

        print(f'positions : {len(deltas)} restored boxes sit exactly on their '
              'saved spots (no animated slide)')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
