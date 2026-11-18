-- Keep the profile row (as a tombstone) when the auth user is deleted.
alter table public.profiles drop constraint profiles_id_fkey;

alter table public.profiles
  alter column username drop not null,
  alter column email drop not null,
  add column deleted_at timestamptz,
  add constraint profiles_deleted_scrubbed check (
    (deleted_at is null and username is not null and email is not null)
    or (deleted_at is not null and username is null and email is null and not is_master)
  );

alter table public.lottery_logs drop constraint lottery_logs_action_check;
alter table public.lottery_logs add constraint lottery_logs_action_check check (action in
  ('user_registered','lottery_started','lottery_cancelled','result_email_sent','account_deleted'));
