// Drizzle ORM schema fixture (native parser, no external tool).
import { pgTable, serial, text, integer, decimal } from "drizzle-orm/pg-core";

export const clients = pgTable("clients", {
  id: serial("id").primaryKey(),
  nom: text("nom").notNull(),
  courriel: text("courriel"),
});

export const commandes = pgTable("commandes", {
  id: serial("id").primaryKey(),
  clientId: integer("client_id").notNull().references(() => clients.id),
  total: decimal("total"),
});

export const lignes = pgTable("lignes", {
  id: serial("id").primaryKey(),
  commandeId: integer("commande_id").notNull().references(() => commandes.id),
  produit: text("produit"),
});
