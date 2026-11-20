-- Test data from the single-draw version is removed.
delete from public.lottery_logs;
delete from public.lottery_results;
delete from public.lotteries;

create table public.draws (
  id         uuid primary key default gen_random_uuid(),
  name       text not null check (char_length(name) between 1 and 50),
  master_id  uuid not null references public.profiles(id),
  created_at timestamptz not null default now(),
  closed_at  timestamptz,
  closed_by  uuid references public.profiles(id)
);
create unique index draws_name_open_ci on public.draws (lower(name)) where closed_at is null;
alter table public.draws enable row level security;

alter table public.profiles
  add column draw_id uuid references public.draws(id),
  add column joined_at timestamptz;
drop index public.profiles_single_master;
alter table public.profiles drop constraint profiles_deleted_scrubbed;
alter table public.profiles drop column is_master;
alter table public.profiles add constraint profiles_deleted_scrubbed check (
  (deleted_at is null and username is not null and email is not null)
  or (deleted_at is not null and username is null and email is null and draw_id is null)
);

alter table public.lotteries add column draw_id uuid not null references public.draws(id);
drop index public.lotteries_single_active;
create unique index lotteries_single_active on public.lotteries (draw_id) where status = 'finished';

alter table public.lottery_logs add column draw_id uuid references public.draws(id);
alter table public.lottery_logs drop constraint lottery_logs_action_check;
alter table public.lottery_logs add constraint lottery_logs_action_check check (action in (
  'user_registered','lottery_started','lottery_cancelled','result_email_sent','account_deleted',
  'draw_created','draw_joined','draw_left','draw_closed'
));
