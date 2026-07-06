-- Diabetes tracker — Supabase/Railway Postgres schema
-- Single patient (Glauber) for the POC.

create table if not exists patients (
    id           bigint generated always as identity primary key,
    name         text not null,
    telegram_id  bigint unique,
    timezone     text not null default 'America/Sao_Paulo',
    created_at   timestamptz not null default now()
);

-- Fast-acting insulin (Humalog). Pure insulin events — taken erratically
-- through the day (meals AND corrections). Meals are tracked separately.
create table if not exists humalog_doses (
    id          bigint generated always as identity primary key,
    patient_id  bigint not null references patients(id) on delete cascade,
    taken_at    timestamptz not null default now(),
    units       numeric(4,1) not null check (units >= 0),
    reason      text,                       -- refeicao | correcao | outro
    note        text,
    created_at  timestamptz not null default now()
);

-- Meals — a DIFFERENT event from the insulin dose. Tracks macros.
create table if not exists meals (
    id           bigint generated always as identity primary key,
    patient_id   bigint not null references patients(id) on delete cascade,
    eaten_at     timestamptz not null default now(),
    carbs_g      integer check (carbs_g >= 0),
    protein_g    integer check (protein_g >= 0),
    meal_tag     text,                      -- cafe | almoco | janta | lanche
    description  text,
    note         text,
    created_at   timestamptz not null default now()
);

-- Basal insulin (Basaglar), ~21:00 daily.
create table if not exists basal_doses (
    id          bigint generated always as identity primary key,
    patient_id  bigint not null references patients(id) on delete cascade,
    taken_at    timestamptz not null default now(),
    units       numeric(4,1),
    status      text not null default 'taken' check (status in ('taken','skipped')),
    note        text,
    created_at  timestamptz not null default now()
);

-- Blood glucose (glicemia), mg/dL.
create table if not exists glucose_readings (
    id           bigint generated always as identity primary key,
    patient_id   bigint not null references patients(id) on delete cascade,
    measured_at  timestamptz not null default now(),
    mg_dl        integer not null check (mg_dl between 10 and 900),
    context      text,                      -- jejum | pre_refeicao | pos_refeicao | dormir | outro
    note         text,
    created_at   timestamptz not null default now()
);

-- Eye drops (colirio, e.g. binadeprosto).
create table if not exists colirio_uses (
    id          bigint generated always as identity primary key,
    patient_id  bigint not null references patients(id) on delete cascade,
    used_at     timestamptz not null default now(),
    eye         text,                       -- od | oe | ambos
    product     text,
    note        text,
    created_at  timestamptz not null default now()
);

create index if not exists idx_humalog_patient_time  on humalog_doses(patient_id, taken_at desc);
create index if not exists idx_meals_patient_time     on meals(patient_id, eaten_at desc);
create index if not exists idx_basal_patient_time     on basal_doses(patient_id, taken_at desc);
create index if not exists idx_glucose_patient_time   on glucose_readings(patient_id, measured_at desc);
create index if not exists idx_colirio_patient_time   on colirio_uses(patient_id, used_at desc);
