-- Modèle de démonstration mcdview : une médiathèque fictive.
-- 3 schémas, PK, FK, commentaires, colonnes d'audit (_idmodificateur).

CREATE SCHEMA catalogue;
CREATE SCHEMA usagers;
CREATE SCHEMA prets;

-- ---------------------------------------------------------------- catalogue

CREATE TABLE catalogue.editeur (
    idediteur integer NOT NULL,
    nom character varying(120) NOT NULL,
    ville character varying(80),
    _idmodificateur integer,
    _datemodification timestamp without time zone DEFAULT now(),
    CONSTRAINT editeur_pk PRIMARY KEY (idediteur)
);

CREATE TABLE catalogue.auteur (
    idauteur integer NOT NULL,
    nom character varying(120) NOT NULL,
    prenom character varying(120),
    anneenaissance smallint,
    _idmodificateur integer,
    _datemodification timestamp without time zone DEFAULT now(),
    CONSTRAINT auteur_pk PRIMARY KEY (idauteur)
);

CREATE TABLE catalogue.genre (
    idgenre integer NOT NULL,
    libelle character varying(80) NOT NULL,
    CONSTRAINT genre_pk PRIMARY KEY (idgenre)
);

CREATE TABLE catalogue.ouvrage (
    idouvrage integer NOT NULL,
    titre character varying(250) NOT NULL,
    isbn character varying(17),
    anneeparution smallint,
    idediteur integer,
    idgenre integer,
    resume text,
    _idmodificateur integer,
    _datemodification timestamp without time zone DEFAULT now(),
    CONSTRAINT ouvrage_pk PRIMARY KEY (idouvrage)
);

CREATE TABLE catalogue.ouvrage_auteur (
    idouvrage integer NOT NULL,
    idauteur integer NOT NULL,
    role character varying(40) DEFAULT 'auteur',
    CONSTRAINT ouvrage_auteur_pk PRIMARY KEY (idouvrage, idauteur)
);

CREATE TABLE catalogue.exemplaire (
    idexemplaire integer NOT NULL,
    idouvrage integer NOT NULL,
    codebarre character varying(20) NOT NULL,
    etat character varying(20) DEFAULT 'bon',
    dateachat date,
    idsite integer,
    _idmodificateur integer,
    _datemodification timestamp without time zone DEFAULT now(),
    CONSTRAINT exemplaire_pk PRIMARY KEY (idexemplaire)
);

-- ------------------------------------------------------------------ usagers

CREATE TABLE usagers.site (
    idsite integer NOT NULL,
    nom character varying(120) NOT NULL,
    adresse text,
    CONSTRAINT site_pk PRIMARY KEY (idsite)
);

CREATE TABLE usagers.abonne (
    idabonne integer NOT NULL,
    nom character varying(120) NOT NULL,
    prenom character varying(120) NOT NULL,
    courriel character varying(250),
    datenaissance date,
    idsite integer,
    dateinscription date DEFAULT now() NOT NULL,
    _idmodificateur integer,
    _datemodification timestamp without time zone DEFAULT now(),
    CONSTRAINT abonne_pk PRIMARY KEY (idabonne)
);

CREATE TABLE usagers.agent (
    idagent integer NOT NULL,
    nom character varying(120) NOT NULL,
    prenom character varying(120) NOT NULL,
    idsite integer,
    CONSTRAINT agent_pk PRIMARY KEY (idagent)
);

-- -------------------------------------------------------------------- prets

CREATE TABLE prets.pret (
    idpret integer NOT NULL,
    idexemplaire integer NOT NULL,
    idabonne integer NOT NULL,
    idagent integer,
    datepret date DEFAULT now() NOT NULL,
    dateretourprevu date NOT NULL,
    dateretour date,
    _idmodificateur integer,
    _datemodification timestamp without time zone DEFAULT now(),
    CONSTRAINT pret_pk PRIMARY KEY (idpret)
);

CREATE TABLE prets.reservation (
    idreservation integer NOT NULL,
    idouvrage integer NOT NULL,
    idabonne integer NOT NULL,
    datereservation timestamp without time zone DEFAULT now() NOT NULL,
    etat character varying(20) DEFAULT 'active' NOT NULL,
    CONSTRAINT reservation_pk PRIMARY KEY (idreservation)
);

CREATE TABLE prets.penalite (
    idpenalite integer NOT NULL,
    idpret integer NOT NULL,
    montant numeric(6,2) NOT NULL,
    motif character varying(120),
    datereglement date,
    _idmodificateur integer,
    _datemodification timestamp without time zone DEFAULT now(),
    CONSTRAINT penalite_pk PRIMARY KEY (idpenalite)
);

-- ---------------------------------------------------------------------- FK

ALTER TABLE catalogue.ouvrage
    ADD CONSTRAINT ouvrage_idediteur_fk FOREIGN KEY (idediteur) REFERENCES catalogue.editeur (idediteur);
ALTER TABLE catalogue.ouvrage
    ADD CONSTRAINT ouvrage_idgenre_fk FOREIGN KEY (idgenre) REFERENCES catalogue.genre (idgenre);
ALTER TABLE catalogue.ouvrage_auteur
    ADD CONSTRAINT ouvrage_auteur_idouvrage_fk FOREIGN KEY (idouvrage) REFERENCES catalogue.ouvrage (idouvrage);
ALTER TABLE catalogue.ouvrage_auteur
    ADD CONSTRAINT ouvrage_auteur_idauteur_fk FOREIGN KEY (idauteur) REFERENCES catalogue.auteur (idauteur);
ALTER TABLE catalogue.exemplaire
    ADD CONSTRAINT exemplaire_idouvrage_fk FOREIGN KEY (idouvrage) REFERENCES catalogue.ouvrage (idouvrage);
ALTER TABLE catalogue.exemplaire
    ADD CONSTRAINT exemplaire_idsite_fk FOREIGN KEY (idsite) REFERENCES usagers.site (idsite);

ALTER TABLE usagers.abonne
    ADD CONSTRAINT abonne_idsite_fk FOREIGN KEY (idsite) REFERENCES usagers.site (idsite);
ALTER TABLE usagers.agent
    ADD CONSTRAINT agent_idsite_fk FOREIGN KEY (idsite) REFERENCES usagers.site (idsite);

ALTER TABLE prets.pret
    ADD CONSTRAINT pret_idexemplaire_fk FOREIGN KEY (idexemplaire) REFERENCES catalogue.exemplaire (idexemplaire);
ALTER TABLE prets.pret
    ADD CONSTRAINT pret_idabonne_fk FOREIGN KEY (idabonne) REFERENCES usagers.abonne (idabonne);
ALTER TABLE prets.pret
    ADD CONSTRAINT pret_idagent_fk FOREIGN KEY (idagent) REFERENCES usagers.agent (idagent);
ALTER TABLE prets.reservation
    ADD CONSTRAINT reservation_idouvrage_fk FOREIGN KEY (idouvrage) REFERENCES catalogue.ouvrage (idouvrage);
ALTER TABLE prets.reservation
    ADD CONSTRAINT reservation_idabonne_fk FOREIGN KEY (idabonne) REFERENCES usagers.abonne (idabonne);
ALTER TABLE prets.penalite
    ADD CONSTRAINT penalite_idpret_fk FOREIGN KEY (idpret) REFERENCES prets.pret (idpret);

-- FK d'audit : chaque _idmodificateur pointe vers l'agent ayant modifié la ligne.
ALTER TABLE catalogue.editeur
    ADD CONSTRAINT editeur_idmodificateur_fk FOREIGN KEY (_idmodificateur) REFERENCES usagers.agent (idagent);
ALTER TABLE catalogue.auteur
    ADD CONSTRAINT auteur_idmodificateur_fk FOREIGN KEY (_idmodificateur) REFERENCES usagers.agent (idagent);
ALTER TABLE catalogue.ouvrage
    ADD CONSTRAINT ouvrage_idmodificateur_fk FOREIGN KEY (_idmodificateur) REFERENCES usagers.agent (idagent);
ALTER TABLE catalogue.exemplaire
    ADD CONSTRAINT exemplaire_idmodificateur_fk FOREIGN KEY (_idmodificateur) REFERENCES usagers.agent (idagent);
ALTER TABLE usagers.abonne
    ADD CONSTRAINT abonne_idmodificateur_fk FOREIGN KEY (_idmodificateur) REFERENCES usagers.agent (idagent);
ALTER TABLE prets.pret
    ADD CONSTRAINT pret_idmodificateur_fk FOREIGN KEY (_idmodificateur) REFERENCES usagers.agent (idagent);
ALTER TABLE prets.penalite
    ADD CONSTRAINT penalite_idmodificateur_fk FOREIGN KEY (_idmodificateur) REFERENCES usagers.agent (idagent);

-- --------------------------------------------------------------- commentaires

COMMENT ON TABLE catalogue.ouvrage IS 'Notice bibliographique : un titre du catalogue, indépendamment de ses exemplaires physiques.';
COMMENT ON TABLE catalogue.exemplaire IS 'Exemplaire physique d''un ouvrage, rattaché à un site.';
COMMENT ON TABLE catalogue.ouvrage_auteur IS 'Association ouvrage-auteur, avec le rôle (auteur, traducteur, illustrateur...).';
COMMENT ON TABLE usagers.abonne IS 'Personne inscrite à la médiathèque, rattachée à son site d''inscription.';
COMMENT ON TABLE prets.pret IS 'Prêt d''un exemplaire à un abonné. dateretour NULL = prêt en cours.';
COMMENT ON TABLE prets.reservation IS 'Réservation d''un ouvrage (pas d''un exemplaire précis) par un abonné.';

COMMENT ON COLUMN catalogue.ouvrage.isbn IS 'ISBN-13 avec tirets, ex. 978-2-07-036822-8.';
COMMENT ON COLUMN catalogue.exemplaire.etat IS 'neuf, bon, usé ou retiré.';
COMMENT ON COLUMN prets.pret.dateretourprevu IS 'Date limite de retour, calculée à la date du prêt (+21 jours par défaut).';
COMMENT ON COLUMN prets.reservation.etat IS 'active, honorée ou annulée.';
