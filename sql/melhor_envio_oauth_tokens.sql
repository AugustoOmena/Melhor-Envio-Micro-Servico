-- Melhor Envio OAuth tokens (PostgREST upsert com Prefer: resolution=merge-duplicates).
-- Execute no SQL Editor do projeto Supabase correto (o mesmo URL/key das Lambdas).

create table if not exists public.melhor_envio_oauth_tokens (
    subject text not null,
    env text not null,
    access_token text not null,
    refresh_token text,
    token_type text not null default 'Bearer',
    scope text,
    expires_at timestamptz,
    updated_at timestamptz not null default timezone('utc', now()),
    primary key (subject, env)
);

comment on table public.melhor_envio_oauth_tokens is
    'Tokens OAuth Melhor Envio; subject fixo admin no backend; env sandbox|production.';
