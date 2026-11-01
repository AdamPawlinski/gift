create table public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  username    text not null,
  email       text not null,
  is_master   boolean not null default false,
  created_at  timestamptz not null default now()
);
create unique index profiles_username_ci on public.profiles (lower(username));
create unique index profiles_single_master on public.profiles (is_master) where is_master;

create table public.lotteries (
  id            uuid primary key default gen_random_uuid(),
  status        text not null check (status in ('finished','cancelled')),
  started_by    uuid not null references public.profiles(id),
  created_at    timestamptz not null default now(),
  cancelled_by  uuid references public.profiles(id),
  cancelled_at  timestamptz
);
create unique index lotteries_single_active on public.lotteries (status) where status = 'finished';

create table public.lottery_results (
  lottery_id   uuid not null references public.lotteries(id) on delete cascade,
  giver_id     uuid not null references public.profiles(id) on delete cascade,
  receiver_id  uuid not null references public.profiles(id) on delete cascade,
  primary key (lottery_id, giver_id),
  unique (lottery_id, receiver_id),
  check (giver_id <> receiver_id)
);

create table public.lottery_logs (
  id          bigint generated always as identity primary key,
  lottery_id  uuid references public.lotteries(id),
  actor_id    uuid references public.profiles(id) on delete set null,
  action      text not null check (action in ('user_registered','lottery_started','lottery_cancelled','result_email_sent')),
  details     jsonb not null default '{}',
  created_at  timestamptz not null default now()
);

alter table public.profiles        enable row level security;
alter table public.lotteries       enable row level security;
alter table public.lottery_results enable row level security;
alter table public.lottery_logs    enable row level security;
