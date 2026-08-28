#!/usr/bin/env python3
"""Structural validation of a generated page. CI runs this on every example.

Checks, without a browser, that a produced HTML page is well-formed enough
and self-consistent: it parses, tags are balanced, no template placeholder
survived, and the data island is valid JSON with at least one table. The
`.table` nodes are built by JS at runtime, so the rendered DOM count is
checked separately by the headless-Chrome pass in grand_banc.py --chrome.

Usage: valider_html.py page1.html [page2.html ...]
"""
import html.parser
import json
import re
import sys

# void elements have no closing tag; everything else must be balanced
VOIDES = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
          'link', 'meta', 'param', 'source', 'track', 'wbr'}


class VerificateurArbre(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.pile = []
        self.erreurs = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOIDES:
            self.pile.append(tag)

    def handle_endtag(self, tag):
        if tag in VOIDES:
            return
        if tag in self.pile:
            # close down to the matching open tag (tolerate optional-close tags)
            while self.pile and self.pile.pop() != tag:
                pass
        else:
            self.erreurs.append(f'</{tag}> sans ouverture')


def valider(chemin):
    html_txt = open(chemin, encoding='utf-8').read()
    problemes = []

    for marqueur in ('__DONNEES__', '__TITRE__', '__LOGO__'):
        if marqueur in html_txt:
            problemes.append(f'placeholder {marqueur} non remplacé')

    v = VerificateurArbre()
    v.feed(html_txt)
    problemes += v.erreurs
    residu = [t for t in v.pile if t not in ('html', 'body', 'head', 'meta',
                                             'li', 'p', 'option')]
    if residu:
        problemes.append(f'balises non fermées : {residu}')

    ilot = re.search(r'const D = (.*?);\nconst plan', html_txt, re.S)
    if not ilot:
        problemes.append('îlot de données introuvable')
    else:
        try:
            donnees = json.loads(ilot.group(1))
            if not donnees.get('tables'):
                problemes.append('aucune table dans les données injectées')
        except json.JSONDecodeError as e:
            problemes.append(f'JSON de données invalide : {e}')

    return problemes


def principal():
    if len(sys.argv) < 2:
        sys.exit('usage: valider_html.py page.html [...]')
    total = 0
    for chemin in sys.argv[1:]:
        problemes = valider(chemin)
        etat = 'FAIL' if problemes else 'ok  '
        print(f'{etat} {chemin}' + (' — ' + '; '.join(problemes) if problemes else ''))
        total += len(problemes)
    sys.exit(1 if total else 0)


if __name__ == '__main__':
    principal()
