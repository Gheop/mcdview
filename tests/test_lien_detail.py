#!/usr/bin/env python3
"""Clicking a foreign-key link shows its detail in the right panel.

A real headless render, driven through the actual pointerdown/pointerup path (a
synthetic click on the link's hit stroke, found at a point free of any table) —
not by calling detaillerLien() directly, so the pan/zoom capture and the
hit-testing are exercised the way a user's click is. Checks:
  - a 1:N link (post -> app_user, ON DELETE SET NULL / ON UPDATE CASCADE) opens a
    panel titled with both tables, showing "un-à-plusieurs" and both actions;
  - a 1:1 link (profile.user_id is UNIQUE) reads as "un-à-un".

Skips cleanly when no Chrome binary is available."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# English identifiers on purpose: test fixtures are public on GitHub. A UNIQUE FK
# column (profile.user_id) exercises the 1:1 detection; the actions exercise the
# ON DELETE / ON UPDATE extraction.
FIXTURE = """
CREATE TABLE app_user (id integer PRIMARY KEY, name character varying(120) NOT NULL);
CREATE TABLE profile (id integer PRIMARY KEY, user_id integer NOT NULL, bio text);
ALTER TABLE profile ADD CONSTRAINT profile_user_uq UNIQUE (user_id);
ALTER TABLE profile ADD CONSTRAINT profile_user_fk FOREIGN KEY (user_id)
  REFERENCES app_user(id) ON DELETE CASCADE;
CREATE TABLE post (id integer PRIMARY KEY, author_id integer, title character varying(200) NOT NULL);
ALTER TABLE post ADD CONSTRAINT post_author_fk FOREIGN KEY (author_id)
  REFERENCES app_user(id) ON DELETE SET NULL ON UPDATE CASCADE;
"""

SONDE = r"""
<script>
window.onerror = function (m) { window._e = m; };
// click the link whose child table has this basename, at a point on its hit
// stroke that is not covered by any table, then read the panel back
function cliquerLien(deNom) {
  var vp = document.getElementById("viewport");
  var paths = [].slice.call(document.querySelectorAll("#liensClic path"));
  for (var j = 0; j < paths.length; j++) {
    var p = paths[j], f = liensVus[+p.dataset.fk];
    if (f.de.split(".")[1] !== deNom) continue;
    var L = p.getTotalLength(), m = p.getScreenCTM();
    for (var i = 1; i < 20; i++) {
      var pt = p.getPointAtLength(L * i / 20);
      var sp = new DOMPoint(pt.x, pt.y).matrixTransform(m);
      var el = document.elementFromPoint(sp.x, sp.y);
      if (el && el.closest("#liensClic path") && !el.closest(".table")) {
        var o = { clientX: sp.x, clientY: sp.y, bubbles: true, pointerId: 1 };
        vp.dispatchEvent(new PointerEvent("pointerdown", o));
        vp.dispatchEvent(new PointerEvent("pointerup", o));
        return { h2: document.querySelector("#panneau h2").textContent,
                 txt: document.getElementById("panneau").textContent };
      }
    }
  }
  return { h2: "", txt: "(aucun point libre)" };
}
window.addEventListener("load", function () {
  setTimeout(function () {
    var r1 = cliquerLien("post");      // 1:N + two actions
    var r2 = cliquerLien("profile");   // 1:1 (unique FK column)
    document.title = JSON.stringify({ err: window._e || "none", r1: r1, r2: r2,
      hits: document.querySelectorAll("#liensClic path").length });
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
        print('test_lien_detail : skipped (no Chrome binary found)')
        return 0
    with tempfile.TemporaryDirectory() as td:
        sql = Path(td) / 'm.sql'
        sql.write_text(FIXTURE)
        page = Path(td) / 'm.html'
        subprocess.run([str(RACINE / 'mcdview.py'), str(sql), '-o', str(page),
                        '--titre', 'Liens'], check=True, capture_output=True)
        page.write_text(page.read_text().replace('</body>', SONDE + '</body>'))
        sortie = subprocess.run(
            [binaire, '--headless=new', '--disable-gpu', '--no-sandbox',
             '--window-size=1600,900', '--virtual-time-budget=6000',
             '--dump-dom', f'file://{page}'],
            capture_output=True, text=True, timeout=60).stdout
        mt = re.search(r'<title>(.*?)</title>', sortie, re.S)
        if not mt or not mt.group(1).startswith('{'):
            print(f'test_lien_detail : FAIL — no measurement (title={mt and mt.group(1)!r})')
            return 1
        r = json.loads(mt.group(1))
        echecs = []
        if r['err'] != 'none':
            echecs.append(f"JS error: {r['err']}")
        if r['hits'] != 2:
            echecs.append(f"{r['hits']} hit-paths, expected 2 (one per visible FK)")
        r1, r2 = r['r1'], r['r2']
        if not ('post' in r1['h2'] and 'app_user' in r1['h2']):
            echecs.append(f"1:N panel title missing endpoints: {r1['h2']!r}")
        if 'un-à-plusieurs' not in r1['txt']:
            echecs.append("1:N panel did not read as un-à-plusieurs")
        if 'ON DELETE SET NULL' not in r1['txt'] or 'ON UPDATE CASCADE' not in r1['txt']:
            echecs.append("1:N panel missing the referential actions")
        if 'profile' not in r2['h2']:
            echecs.append(f"1:1 panel title wrong: {r2['h2']!r}")
        if 'un-à-un' not in r2['txt']:
            echecs.append("1:1 (unique FK column) not detected as un-à-un")
        if 'ON DELETE CASCADE' not in r2['txt']:
            echecs.append("1:1 panel missing ON DELETE CASCADE")
        if echecs:
            print('test_lien_detail : FAIL')
            for e in echecs:
                print('  ' + e)
            return 1
        print('lien détail : clic sur un lien → panneau (endpoints, cardinalité, actions) OK')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
