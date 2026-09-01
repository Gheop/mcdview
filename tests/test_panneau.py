#!/usr/bin/env python3
"""Detail-panel intro is remembered across loads.

The panel plays an open-then-close intro on load. Replaying it on every reload
(iframe / time-lapse) is annoying, so a viewer who has folded the panel starts
collapsed with no intro next time. This checks, in a real headless render:
  - first visit (empty localStorage): the intro plays (body gets intro-panneau);
  - clicking the toggle writes the choice to localStorage (mcdview:panneau);
  - a remembered "reduit" choice skips the intro on the next load (no
    intro-panneau), while the panel stays collapsed.

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


def titre(binaire, profil, chemin_html):
    sortie = subprocess.run(
        [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
         f'--user-data-dir={profil}', '--window-size=1600,900',
         '--virtual-time-budget=3000', '--dump-dom', f'file://{chemin_html}'],
        capture_output=True, text=True, timeout=60).stdout
    m = re.search(r'<title>(.*?)</title>', sortie, re.S)
    return m.group(1) if m else ''


def principal():
    binaire = chrome_binaire()
    if not binaire:
        print('test_panneau : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        page = td / 'chinook.html'
        subprocess.run(
            [str(RACINE / 'mcdview.py'), str(RACINE / 'exemples' / 'chinook.sql'),
             '-o', str(page), '--titre', 'Chinook'], check=True, capture_output=True)
        source = page.read_text()
        profil = td / 'profil'
        echecs = []

        # first visit (empty localStorage): intro plays, then fold and persist
        p1 = td / 'p1.html'
        p1.write_text(source.replace('</body>',
            "<script>window.addEventListener('load',function(){setTimeout(function(){"
            "var intro=document.body.classList.contains('intro-panneau');"
            "document.getElementById('togglePanneau').click();"
            "var ls=null;try{ls=localStorage.getItem('mcdview:panneau');}catch(e){}"
            "document.title=JSON.stringify({intro:intro,ls:ls});"
            "},80);});</script></body>"))
        t1 = titre(binaire, str(profil), str(p1))
        if not t1.startswith('{'):
            print(f'test_panneau : FAIL — no measurement, first visit (title={t1!r})')
            return 1
        r1 = json.loads(t1)
        if not r1['intro']:
            echecs.append('first visit: intro did not play (intro-panneau missing)')
        if r1['ls'] is None:
            echecs.append('toggling the panel did not persist the choice to localStorage')

        # seed the remembered "reduit" choice, then load fresh and check the skip
        seed = td / 'seed.html'
        seed.write_text(source.replace('</body>',
            "<script>window.addEventListener('load',function(){"
            "try{localStorage.setItem('mcdview:panneau','reduit');}catch(e){}"
            "document.title='SEEDED';});</script></body>"))
        if titre(binaire, str(profil), str(seed)) != 'SEEDED':
            print('test_panneau : FAIL — could not seed the panel preference')
            return 1
        p2 = td / 'p2.html'
        p2.write_text(source.replace('</body>',
            "<script>window.addEventListener('load',function(){setTimeout(function(){"
            "document.title=JSON.stringify({"
            "reduit:document.body.classList.contains('panneau-reduit'),"
            "intro:document.body.classList.contains('intro-panneau')});"
            "},80);});</script></body>"))
        t2 = titre(binaire, str(profil), str(p2))
        if not t2.startswith('{'):
            print(f'test_panneau : FAIL — no measurement, remembered (title={t2!r})')
            return 1
        r2 = json.loads(t2)
        if r2['intro']:
            echecs.append('remembered "reduit": intro still played (should be skipped)')
        if not r2['reduit']:
            echecs.append('remembered "reduit": panel did not start collapsed')

        if echecs:
            print('test_panneau : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('panneau : intro on first visit, choice persisted, intro skipped when remembered collapsed')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
