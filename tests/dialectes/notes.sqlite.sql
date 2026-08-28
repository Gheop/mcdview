-- SQLite dialect fixture: double-quoted or bare names, AUTOINCREMENT,
-- everything on one line, inline REFERENCES, loose types.
CREATE TABLE "carnet" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "titre" TEXT NOT NULL);
CREATE TABLE "note" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "carnet_id" INTEGER NOT NULL REFERENCES "carnet"("id"), "texte" TEXT, "cree_le" TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE "etiquette" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "libelle" TEXT NOT NULL);
CREATE TABLE "note_etiquette" ("note_id" INTEGER NOT NULL REFERENCES "note"("id"), "etiquette_id" INTEGER NOT NULL REFERENCES "etiquette"("id"), PRIMARY KEY ("note_id", "etiquette_id"));
