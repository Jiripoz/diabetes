-- Diabetes tracker — Supabase (Postgres) schema
-- Single patient (Glauber) for the POC. Run this in the Supabase SQL editor.

-- One row per patient. For the POC we expect a single row.
create table if not exists patients (
    id           bigint generated always as identity primary key,
    name         text not null,
    telegram_id  bigint unique,            -- Telegram numeric user id (only this user may log)
    timezone     text not null default 'America/Sao_Paulo',
    created_at   timestamptz not null default now()
);

-- Fast-acting insulin (Humalog) doses, usually tied to a meal.
create table if not exists humalog_doses (
    id          bigint generated always as identity primary key,
    patient_id  bigint not null references patients(id) on delete cascade,
    taken_at    timestamptz not null default now(),
    units       numeric(4,1) not null check (units >= 0),
    meal_tag    text,                       -- cafe | almoco | janta | correcao | lanche
    carbs_g     integer,                    -- optional carbs for context
    note        text,
    created_at  timestamptz not null default now()
);

-- Basal insulin (Basaglar), scheduled ~21:00 daily. Confirm taken/skipped.
create table if not exists basal_doses (
    id          bigint generated always as identity primary key,
    patient_id  bigint not null references patients(id) on delete cascade,
    taken_at    timestamptz not null default now(),
    units       numeric(4,1),               -- null = confirmed without recording amount
    status      text not null default 'taken' check (status in ('taken','skipped')),
    note        text,
    created_at  timestamptz not null default now()
);

-- Blood glucose (glicemia) readings, mg/dL.
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
    eye         text,                       -- od (direito) | oe (esquerdo) | ambos
    product     text,
    note        text,
    created_at  timestamptz not null default now()
);

create index if not exists idx_humalog_patient_time  on humalog_doses(patient_id, taken_at desc);
create index if not exists idx_basal_patient_time     on basal_doses(patient_id, taken_at desc);
create index if not exists idx_glucose_patient_time   on glucose_readings(patient_id, measured_at desc);
create index if not exists idx_colirio_patient_time   on colirio_uses(patient_id, used_at desc);
