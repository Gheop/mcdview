# mcdview

<img src="logo.svg" width="96" align="right" alt="mcdview logo">

Interactive HTML explorer for a PostgreSQL data model. From a DDL file
(`CREATE TABLE ...`), mcdview generates a self-contained page — no server,
no dependency — to browse the model: overview of tables grouped by schema,
click a table to isolate it with its related tables, field detail panel,
search box.

**[Live demo](https://gheop.github.io/mcdview/exemples/mediatheque.html)** —
a fictional library model (12 tables, 3 schemas).

[![mcdview showing a table isolated with its related tables](docs/screenshot.webp)](https://gheop.github.io/mcdview/exemples/mediatheque.html)

## Usage

```bash
./mcdview.py model.sql
./mcdview.py model.sql -o explorer.html --titre "My project"
```

Then open the generated HTML file in a browser.

In the page:

- **wheel**: zoom, **drag**: pan;
- **click a table**: isolates it with its related tables (the others fade
  out, the view re-frames) and shows its detail on the right — fields,
  types, NOT NULL, PK 🔑, clickable FK 🔗, table and column comments,
  list of referencing tables;
- **Escape** or "vue générale": back to the full, re-framed overview;
- **search** with table name autocompletion.

## Options

| Option | Effect |
|---|---|
| `-o, --sortie FILE` | Output HTML file (default: `<sql>.html`) |
| `--titre TEXT` | Title shown in the page (default: file name) |
| `--dbm FILE` | Reuse table positions from a pgModeler model instead of automatic layout |
| `--fk-audit REGEX` | Tag as "audit" the FKs whose constraint name matches: hidden by default, shown back with a checkbox |
| `--lang {fr,en}` | Language of the page UI (default: `fr`) |

Without `--dbm`, mcdview computes an automatic layout: one zone per schema,
tables arranged in balanced columns, related tables pulled together.

`--fk-audit` is for models where every table carries audit columns
(`created_by`, `modified_by`...) pointing to a users table: those FKs turn
that table into a hub linked to everything and clutter the graph.

## What mcdview reads from the DDL

- `CREATE TABLE schema.table (...)`: columns, types, NOT NULL, DEFAULT,
  `CONSTRAINT ... PRIMARY KEY`;
- `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ...`;
- `COMMENT ON TABLE` and `COMMENT ON COLUMN`.

Tables must be schema-qualified. A qualified `pg_dump -s` dump works.

## Example

`exemples/mediatheque.html` ([live](https://gheop.github.io/mcdview/exemples/mediatheque.html))
is generated from `exemples/mediatheque.sql`, a fictional library model
(12 tables, 3 schemas, 21 FKs including 7 audit FKs):

```bash
./mcdview.py exemples/mediatheque.sql --titre "Médiathèque (démo)" --fk-audit '_idmodificateur_fk$' --lang en
```

## Development

Plain Python 3, no dependency. All the rendering lives in
`templates/explorateur.html` (inline CSS/JS); the data is injected as JSON
in place of `__DONNEES__`.

## Changelog

### v0.2.0 — English UI (2026-08-28)

- `--lang {fr,en}` option: language of the generated page's interface
  (search box, help text, detail panel labels)
- The live demo now uses the English UI

### v0.1.1 — Public release (2026-08-28)

- Fictional library demo (`exemples/mediatheque.sql`) with a live version
  on GitHub Pages
- README in English, screenshot
- Published on GitHub

### v0.1.0 — First standalone version (2026-08-27)

- Automatic table layout (one zone per schema, balanced columns, related
  tables pulled together) — the pgModeler `.dbm` becomes optional
- `--titre`, `--fk-audit`, `--dbm`, `-o` options
- SVG logo, "audit FK" checkbox hidden when no FK matches
