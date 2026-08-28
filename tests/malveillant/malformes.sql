-- Structurally broken DDL: mcdview must finish quickly and not crash.
CREATE TABLE public.jamais_fermee (
    id integer NOT NULL,
    nom text
CREATE TABLE public.autre (
    id integer NOT NULL,
    CONSTRAINT autre_pk PRIMARY KEY (id)
);
ALTER TABLE public.orpheline ADD CONSTRAINT x FOREIGN KEY (a) REFERENCES public.absente (b);
COMMENT ON TABLE public.inexistante IS 'ceci ne colle à aucune table';
CREATE TABLE ();
CREATE TABLE public.vide (
);
