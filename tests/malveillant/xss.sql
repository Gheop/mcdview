-- XSS payloads in every field mcdview actually parses and injects: DEFAULT
-- values, table comments, column comments. test_securite.py checks that the
-- JSON data island escapes every '<' (no markup can break out of it) and
-- that ech() renders the payloads as inert text.
CREATE TABLE public.piege (
    id integer NOT NULL,
    charge text DEFAULT '</script><script>alert(1)</script>',
    image text DEFAULT '"><img src=x onerror=alert(2)>',
    lien text DEFAULT 'javascript:alert(3)',
    CONSTRAINT piege_pk PRIMARY KEY (id)
);
COMMENT ON TABLE public.piege IS '</script><svg onload=alert(4)>';
COMMENT ON COLUMN public.piege.charge IS '<img src=x onerror=alert(5)>';

CREATE TABLE public.normale (
    id integer NOT NULL,
    ref integer,
    CONSTRAINT normale_pk PRIMARY KEY (id)
);
ALTER TABLE public.normale
    ADD CONSTRAINT normale_ref_fk FOREIGN KEY (ref) REFERENCES public.piege (id);
