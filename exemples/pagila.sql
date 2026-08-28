-- Pagila — sample DVD rental database for PostgreSQL (schema only).
-- Source: https://github.com/devrimgunduz/pagila (PostgreSQL/BSD license).
-- Trimmed for mcdview: tables, keys and comments only (no data, views or functions).

CREATE TABLE public.customer (
    customer_id integer DEFAULT nextval('public.customer_customer_id_seq'::regclass) NOT NULL,
    store_id integer NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    email text,
    address_id integer NOT NULL,
    activebool boolean DEFAULT true NOT NULL,
    create_date date DEFAULT CURRENT_DATE NOT NULL,
    last_update timestamp with time zone DEFAULT now(),
    active integer,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.actor (
    actor_id integer DEFAULT nextval('public.actor_actor_id_seq'::regclass) NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.category (
    category_id integer DEFAULT nextval('public.category_category_id_seq'::regclass) NOT NULL,
    name text NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.film (
    film_id integer DEFAULT nextval('public.film_film_id_seq'::regclass) NOT NULL,
    title text NOT NULL,
    description text,
    release_year public.year,
    language_id integer NOT NULL,
    original_language_id integer,
    rental_duration smallint DEFAULT 3 NOT NULL,
    rental_rate numeric(4,2) DEFAULT 4.99 NOT NULL,
    length smallint,
    replacement_cost numeric(5,2) DEFAULT 19.99 NOT NULL,
    rating public.mpaa_rating DEFAULT 'G'::public.mpaa_rating,
    last_update timestamp with time zone DEFAULT now() NOT NULL,
    special_features text[],
    fulltext tsvector NOT NULL,
    length_hours numeric(4,2) GENERATED ALWAYS AS (round(length / 60.0, 2)) VIRTUAL
);

CREATE TABLE public.film_actor (
    actor_id integer NOT NULL,
    film_id integer NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.film_category (
    film_id integer NOT NULL,
    category_id integer NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.film_embedding (
    film_id integer NOT NULL,
    embedding public.vector(20) NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.address (
    address_id integer DEFAULT nextval('public.address_address_id_seq'::regclass) NOT NULL,
    address text NOT NULL,
    address2 text,
    district text NOT NULL,
    city_id integer NOT NULL,
    postal_code text,
    phone text NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.city (
    city_id integer DEFAULT nextval('public.city_city_id_seq'::regclass) NOT NULL,
    city text NOT NULL,
    country_id integer NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.country (
    country_id integer DEFAULT nextval('public.country_country_id_seq'::regclass) NOT NULL,
    country text NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.inventory (
    inventory_id integer DEFAULT nextval('public.inventory_inventory_id_seq'::regclass) NOT NULL,
    film_id integer NOT NULL,
    store_id integer NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.language (
    language_id integer DEFAULT nextval('public.language_language_id_seq'::regclass) NOT NULL,
    name text NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.payment (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL,
    PRIMARY KEY (payment_date, payment_id)
)
PARTITION BY RANGE (payment_date);

CREATE TABLE public.payment_p2022_01 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_02 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_03 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_04 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_05 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_06 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_07 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_08 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_09 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_10 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_11 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2022_12 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_01 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_02 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_03 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_04 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_05 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_06 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_07 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_08 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_09 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_10 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_11 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2023_12 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_01 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_02 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_03 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_04 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_05 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_06 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_07 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_08 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_09 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_10 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_11 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2024_12 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_01 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_02 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_03 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_04 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_05 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_06 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_07 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_08 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_09 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_10 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_11 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2025_12 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2026_01 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2026_02 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2026_03 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2026_04 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2026_05 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2026_06 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.payment_p2026_07 (
    payment_id integer DEFAULT nextval('public.payment_payment_id_seq'::regclass) NOT NULL,
    customer_id integer NOT NULL,
    staff_id integer NOT NULL,
    rental_id integer NOT NULL,
    amount numeric(5,2) NOT NULL,
    payment_date timestamp with time zone NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.rental (
    rental_id integer DEFAULT nextval('public.rental_rental_id_seq'::regclass) NOT NULL,
    rental_date timestamp with time zone NOT NULL,
    inventory_id integer NOT NULL,
    customer_id integer NOT NULL,
    return_date timestamp with time zone,
    staff_id integer NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL,
    uuid uuid DEFAULT uuidv7() NOT NULL
);

CREATE TABLE public.staff (
    staff_id integer DEFAULT nextval('public.staff_staff_id_seq'::regclass) NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    address_id integer NOT NULL,
    email text,
    store_id integer NOT NULL,
    active boolean DEFAULT true NOT NULL,
    username text NOT NULL,
    password text,
    last_update timestamp with time zone DEFAULT now() NOT NULL,
    picture bytea
);

CREATE TABLE public.store (
    store_id integer DEFAULT nextval('public.store_store_id_seq'::regclass) NOT NULL,
    manager_staff_id integer NOT NULL,
    address_id integer NOT NULL,
    last_update timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_01 FOR VALUES FROM ('2022-01-01 00:00:00+00') TO ('2022-02-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_02 FOR VALUES FROM ('2022-02-01 00:00:00+00') TO ('2022-03-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_03 FOR VALUES FROM ('2022-03-01 00:00:00+00') TO ('2022-04-01 01:00:00+01');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_04 FOR VALUES FROM ('2022-04-01 01:00:00+01') TO ('2022-05-01 01:00:00+01');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_05 FOR VALUES FROM ('2022-05-01 01:00:00+01') TO ('2022-06-01 01:00:00+01');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_06 FOR VALUES FROM ('2022-06-01 01:00:00+01') TO ('2022-07-01 01:00:00+01');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_07 FOR VALUES FROM ('2022-07-01 01:00:00+01') TO ('2022-08-01 01:00:00+01');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_08 FOR VALUES FROM ('2022-08-01 00:00:00+00') TO ('2022-09-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_09 FOR VALUES FROM ('2022-09-01 00:00:00+00') TO ('2022-10-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_10 FOR VALUES FROM ('2022-10-01 00:00:00+00') TO ('2022-11-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_11 FOR VALUES FROM ('2022-11-01 00:00:00+00') TO ('2022-12-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2022_12 FOR VALUES FROM ('2022-12-01 00:00:00+00') TO ('2023-01-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_01 FOR VALUES FROM ('2023-01-01 00:00:00+00') TO ('2023-02-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_02 FOR VALUES FROM ('2023-02-01 00:00:00+00') TO ('2023-03-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_03 FOR VALUES FROM ('2023-03-01 00:00:00+00') TO ('2023-04-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_04 FOR VALUES FROM ('2023-04-01 00:00:00+00') TO ('2023-05-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_05 FOR VALUES FROM ('2023-05-01 00:00:00+00') TO ('2023-06-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_06 FOR VALUES FROM ('2023-06-01 00:00:00+00') TO ('2023-07-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_07 FOR VALUES FROM ('2023-07-01 00:00:00+00') TO ('2023-08-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_08 FOR VALUES FROM ('2023-08-01 00:00:00+00') TO ('2023-09-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_09 FOR VALUES FROM ('2023-09-01 00:00:00+00') TO ('2023-10-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_10 FOR VALUES FROM ('2023-10-01 00:00:00+00') TO ('2023-11-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_11 FOR VALUES FROM ('2023-11-01 00:00:00+00') TO ('2023-12-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2023_12 FOR VALUES FROM ('2023-12-01 00:00:00+00') TO ('2024-01-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_01 FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2024-02-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_02 FOR VALUES FROM ('2024-02-01 00:00:00+00') TO ('2024-03-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_03 FOR VALUES FROM ('2024-03-01 00:00:00+00') TO ('2024-04-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_04 FOR VALUES FROM ('2024-04-01 00:00:00+00') TO ('2024-05-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_05 FOR VALUES FROM ('2024-05-01 00:00:00+00') TO ('2024-06-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_06 FOR VALUES FROM ('2024-06-01 00:00:00+00') TO ('2024-07-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_07 FOR VALUES FROM ('2024-07-01 00:00:00+00') TO ('2024-08-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_08 FOR VALUES FROM ('2024-08-01 00:00:00+00') TO ('2024-09-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_09 FOR VALUES FROM ('2024-09-01 00:00:00+00') TO ('2024-10-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_10 FOR VALUES FROM ('2024-10-01 00:00:00+00') TO ('2024-11-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_11 FOR VALUES FROM ('2024-11-01 00:00:00+00') TO ('2024-12-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2024_12 FOR VALUES FROM ('2024-12-01 00:00:00+00') TO ('2025-01-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_01 FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_02 FOR VALUES FROM ('2025-02-01 00:00:00+00') TO ('2025-03-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_03 FOR VALUES FROM ('2025-03-01 00:00:00+00') TO ('2025-04-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_04 FOR VALUES FROM ('2025-04-01 00:00:00+00') TO ('2025-05-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_05 FOR VALUES FROM ('2025-05-01 00:00:00+00') TO ('2025-06-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_06 FOR VALUES FROM ('2025-06-01 00:00:00+00') TO ('2025-07-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_07 FOR VALUES FROM ('2025-07-01 00:00:00+00') TO ('2025-08-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_08 FOR VALUES FROM ('2025-08-01 00:00:00+00') TO ('2025-09-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_09 FOR VALUES FROM ('2025-09-01 00:00:00+00') TO ('2025-10-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_10 FOR VALUES FROM ('2025-10-01 00:00:00+00') TO ('2025-11-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_11 FOR VALUES FROM ('2025-11-01 00:00:00+00') TO ('2025-12-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2025_12 FOR VALUES FROM ('2025-12-01 00:00:00+00') TO ('2026-01-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2026_01 FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2026_02 FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2026_03 FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2026_04 FOR VALUES FROM ('2026-04-01 00:00:00+00') TO ('2026-05-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2026_05 FOR VALUES FROM ('2026-05-01 00:00:00+00') TO ('2026-06-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2026_06 FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');

ALTER TABLE ONLY public.payment ATTACH PARTITION public.payment_p2026_07 FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');

ALTER TABLE ONLY public.actor
    ADD CONSTRAINT actor_pkey PRIMARY KEY (actor_id);

ALTER TABLE ONLY public.address
    ADD CONSTRAINT address_pkey PRIMARY KEY (address_id);

ALTER TABLE ONLY public.category
    ADD CONSTRAINT category_pkey PRIMARY KEY (category_id);

ALTER TABLE ONLY public.city
    ADD CONSTRAINT city_pkey PRIMARY KEY (city_id);

ALTER TABLE ONLY public.country
    ADD CONSTRAINT country_pkey PRIMARY KEY (country_id);

ALTER TABLE ONLY public.customer
    ADD CONSTRAINT customer_pkey PRIMARY KEY (customer_id);

ALTER TABLE ONLY public.film_actor
    ADD CONSTRAINT film_actor_pkey PRIMARY KEY (actor_id, film_id);

ALTER TABLE ONLY public.film_category
    ADD CONSTRAINT film_category_pkey PRIMARY KEY (film_id, category_id);

ALTER TABLE ONLY public.film_embedding
    ADD CONSTRAINT film_embedding_pkey PRIMARY KEY (film_id);

ALTER TABLE ONLY public.film
    ADD CONSTRAINT film_pkey PRIMARY KEY (film_id);

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (inventory_id);

ALTER TABLE ONLY public.language
    ADD CONSTRAINT language_pkey PRIMARY KEY (language_id);

ALTER TABLE ONLY public.rental
    ADD CONSTRAINT rental_pkey PRIMARY KEY (rental_id);

ALTER TABLE ONLY public.staff
    ADD CONSTRAINT staff_pkey PRIMARY KEY (staff_id);

ALTER TABLE ONLY public.store
    ADD CONSTRAINT store_pkey PRIMARY KEY (store_id);

ALTER TABLE ONLY public.address
    ADD CONSTRAINT address_city_id_fkey FOREIGN KEY (city_id) REFERENCES public.city(city_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.city
    ADD CONSTRAINT city_country_id_fkey FOREIGN KEY (country_id) REFERENCES public.country(country_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.customer
    ADD CONSTRAINT customer_address_id_fkey FOREIGN KEY (address_id) REFERENCES public.address(address_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.customer
    ADD CONSTRAINT customer_store_id_fkey FOREIGN KEY (store_id) REFERENCES public.store(store_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.film_actor
    ADD CONSTRAINT film_actor_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actor(actor_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.film_actor
    ADD CONSTRAINT film_actor_film_id_fkey FOREIGN KEY (film_id) REFERENCES public.film(film_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.film_category
    ADD CONSTRAINT film_category_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.category(category_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.film_category
    ADD CONSTRAINT film_category_film_id_fkey FOREIGN KEY (film_id) REFERENCES public.film(film_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.film_embedding
    ADD CONSTRAINT film_embedding_film_id_fkey FOREIGN KEY (film_id) REFERENCES public.film(film_id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public.film
    ADD CONSTRAINT film_language_id_fkey FOREIGN KEY (language_id) REFERENCES public.language(language_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.film
    ADD CONSTRAINT film_original_language_id_fkey FOREIGN KEY (original_language_id) REFERENCES public.language(language_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_film_id_fkey FOREIGN KEY (film_id) REFERENCES public.film(film_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_store_id_fkey FOREIGN KEY (store_id) REFERENCES public.store(store_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.payment_p2022_01
    ADD CONSTRAINT payment_p2022_01_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customer(customer_id);

ALTER TABLE ONLY public.payment_p2022_01
    ADD CONSTRAINT payment_p2022_01_rental_id_fkey FOREIGN KEY (rental_id) REFERENCES public.rental(rental_id);

ALTER TABLE ONLY public.payment_p2022_01
    ADD CONSTRAINT payment_p2022_01_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(staff_id);

ALTER TABLE ONLY public.payment_p2022_02
    ADD CONSTRAINT payment_p2022_02_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customer(customer_id);

ALTER TABLE ONLY public.payment_p2022_02
    ADD CONSTRAINT payment_p2022_02_rental_id_fkey FOREIGN KEY (rental_id) REFERENCES public.rental(rental_id);

ALTER TABLE ONLY public.payment_p2022_02
    ADD CONSTRAINT payment_p2022_02_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(staff_id);

ALTER TABLE ONLY public.payment_p2022_03
    ADD CONSTRAINT payment_p2022_03_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customer(customer_id);

ALTER TABLE ONLY public.payment_p2022_03
    ADD CONSTRAINT payment_p2022_03_rental_id_fkey FOREIGN KEY (rental_id) REFERENCES public.rental(rental_id);

ALTER TABLE ONLY public.payment_p2022_03
    ADD CONSTRAINT payment_p2022_03_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(staff_id);

ALTER TABLE ONLY public.payment_p2022_04
    ADD CONSTRAINT payment_p2022_04_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customer(customer_id);

ALTER TABLE ONLY public.payment_p2022_04
    ADD CONSTRAINT payment_p2022_04_rental_id_fkey FOREIGN KEY (rental_id) REFERENCES public.rental(rental_id);

ALTER TABLE ONLY public.payment_p2022_04
    ADD CONSTRAINT payment_p2022_04_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(staff_id);

ALTER TABLE ONLY public.payment_p2022_05
    ADD CONSTRAINT payment_p2022_05_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customer(customer_id);

ALTER TABLE ONLY public.payment_p2022_05
    ADD CONSTRAINT payment_p2022_05_rental_id_fkey FOREIGN KEY (rental_id) REFERENCES public.rental(rental_id);

ALTER TABLE ONLY public.payment_p2022_05
    ADD CONSTRAINT payment_p2022_05_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(staff_id);

ALTER TABLE ONLY public.payment_p2022_06
    ADD CONSTRAINT payment_p2022_06_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customer(customer_id);

ALTER TABLE ONLY public.payment_p2022_06
    ADD CONSTRAINT payment_p2022_06_rental_id_fkey FOREIGN KEY (rental_id) REFERENCES public.rental(rental_id);

ALTER TABLE ONLY public.payment_p2022_06
    ADD CONSTRAINT payment_p2022_06_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(staff_id);

ALTER TABLE ONLY public.rental
    ADD CONSTRAINT rental_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customer(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.rental
    ADD CONSTRAINT rental_inventory_id_fkey FOREIGN KEY (inventory_id) REFERENCES public.inventory(inventory_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.rental
    ADD CONSTRAINT rental_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.staff(staff_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.staff
    ADD CONSTRAINT staff_address_id_fkey FOREIGN KEY (address_id) REFERENCES public.address(address_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.staff
    ADD CONSTRAINT staff_store_id_fkey FOREIGN KEY (store_id) REFERENCES public.store(store_id);

ALTER TABLE ONLY public.store
    ADD CONSTRAINT store_address_id_fkey FOREIGN KEY (address_id) REFERENCES public.address(address_id) ON UPDATE CASCADE ON DELETE RESTRICT;
