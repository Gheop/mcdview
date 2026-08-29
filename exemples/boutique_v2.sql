-- Fictional shop schema, version 2 — the newer model in the --diff demo.
-- Changes vs v1: 'avis' added, 'panier' removed, columns added (slug, sku,
-- telephone, statut, remise), prix/total retyped to bigint, two new FKs.
-- Public domain (CC0).

CREATE TABLE categorie (
    id serial PRIMARY KEY,
    nom text NOT NULL,
    slug text
);

CREATE TABLE produit (
    id serial PRIMARY KEY,
    nom text NOT NULL,
    prix bigint NOT NULL,
    categorie_id integer,
    sku text
);

CREATE TABLE client (
    id serial PRIMARY KEY,
    nom text NOT NULL,
    email text,
    telephone text
);

CREATE TABLE commande (
    id serial PRIMARY KEY,
    client_id integer NOT NULL,
    passee_le date NOT NULL,
    total bigint,
    statut text
);

CREATE TABLE ligne (
    id serial PRIMARY KEY,
    commande_id integer NOT NULL,
    produit_id integer NOT NULL,
    quantite integer NOT NULL,
    remise numeric(5,2)
);

CREATE TABLE avis (
    id serial PRIMARY KEY,
    produit_id integer NOT NULL,
    client_id integer NOT NULL,
    note integer NOT NULL,
    commentaire text
);

ALTER TABLE ONLY produit ADD CONSTRAINT produit_categorie_fk FOREIGN KEY (categorie_id) REFERENCES categorie(id);
ALTER TABLE ONLY commande ADD CONSTRAINT commande_client_fk FOREIGN KEY (client_id) REFERENCES client(id);
ALTER TABLE ONLY ligne ADD CONSTRAINT ligne_commande_fk FOREIGN KEY (commande_id) REFERENCES commande(id);
ALTER TABLE ONLY ligne ADD CONSTRAINT ligne_produit_fk FOREIGN KEY (produit_id) REFERENCES produit(id);
ALTER TABLE ONLY avis ADD CONSTRAINT avis_produit_fk FOREIGN KEY (produit_id) REFERENCES produit(id);
ALTER TABLE ONLY avis ADD CONSTRAINT avis_client_fk FOREIGN KEY (client_id) REFERENCES client(id);
