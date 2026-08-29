-- Fictional shop schema, version 1 — the baseline for the --diff demo.
-- Public domain (CC0): a throwaway model to show mcdview's schema diff.

CREATE TABLE categorie (
    id serial PRIMARY KEY,
    nom text NOT NULL
);

CREATE TABLE produit (
    id serial PRIMARY KEY,
    nom text NOT NULL,
    prix numeric(10,2) NOT NULL,
    categorie_id integer
);

CREATE TABLE client (
    id serial PRIMARY KEY,
    nom text NOT NULL,
    email text
);

CREATE TABLE commande (
    id serial PRIMARY KEY,
    client_id integer NOT NULL,
    passee_le date NOT NULL,
    total numeric(10,2)
);

CREATE TABLE ligne (
    id serial PRIMARY KEY,
    commande_id integer NOT NULL,
    produit_id integer NOT NULL,
    quantite integer NOT NULL
);

-- dropped in v2
CREATE TABLE panier (
    id serial PRIMARY KEY,
    client_id integer NOT NULL
);

ALTER TABLE ONLY produit ADD CONSTRAINT produit_categorie_fk FOREIGN KEY (categorie_id) REFERENCES categorie(id);
ALTER TABLE ONLY commande ADD CONSTRAINT commande_client_fk FOREIGN KEY (client_id) REFERENCES client(id);
ALTER TABLE ONLY ligne ADD CONSTRAINT ligne_commande_fk FOREIGN KEY (commande_id) REFERENCES commande(id);
ALTER TABLE ONLY ligne ADD CONSTRAINT ligne_produit_fk FOREIGN KEY (produit_id) REFERENCES produit(id);
ALTER TABLE ONLY panier ADD CONSTRAINT panier_client_fk FOREIGN KEY (client_id) REFERENCES client(id);
