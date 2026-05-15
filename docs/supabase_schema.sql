-- Smart Study Planner - Phase 3 Supabase Schema
-- Run this SQL in Supabase SQL Editor.

create extension if not exists "pgcrypto";

create table if not exists public.student_profiles (
    id uuid primary key default gen_random_uuid(),
    email text not null unique,
    full_name text,
    preferred_language text default 'en',
    study_style text,
    preferred_study_hours text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.courses (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.student_profiles(id) on delete cascade,
    name text not null,
    syllabus_topics text[] not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (student_id, name)
);

create table if not exists public.exams (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.student_profiles(id) on delete cascade,
    course_id uuid not null references public.courses(id) on delete cascade,
    exam_date date not null,
    target_score integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (student_id, course_id)
);

create table if not exists public.study_tasks (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.student_profiles(id) on delete cascade,
    course_id uuid not null references public.courses(id) on delete cascade,
    exam_id uuid references public.exams(id) on delete set null,
    task_date date not null,
    topic text not null,
    details text,
    hours numeric(4, 1) not null default 1.0,
    checkpoint boolean not null default false,
    completed boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.quiz_scores (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.student_profiles(id) on delete cascade,
    course_id uuid references public.courses(id) on delete set null,
    topic text,
    correct integer not null default 0,
    total integer not null default 0,
    score_percent numeric(5, 2) not null default 0,
    attempted_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.weak_topics (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references public.student_profiles(id) on delete cascade,
    course_id uuid references public.courses(id) on delete set null,
    topic text not null,
    severity_score numeric(5, 2) not null default 0,
    source text default 'manual',
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (student_id, course_id, topic)
);

create index if not exists idx_courses_student_id on public.courses(student_id);
create index if not exists idx_exams_student_course on public.exams(student_id, course_id);
create index if not exists idx_study_tasks_student_course on public.study_tasks(student_id, course_id);
create index if not exists idx_quiz_scores_student_time on public.quiz_scores(student_id, attempted_at desc);
create index if not exists idx_weak_topics_student on public.weak_topics(student_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_student_profiles_updated_at on public.student_profiles;
create trigger trg_student_profiles_updated_at
before update on public.student_profiles
for each row execute function public.set_updated_at();

drop trigger if exists trg_courses_updated_at on public.courses;
create trigger trg_courses_updated_at
before update on public.courses
for each row execute function public.set_updated_at();

drop trigger if exists trg_exams_updated_at on public.exams;
create trigger trg_exams_updated_at
before update on public.exams
for each row execute function public.set_updated_at();

drop trigger if exists trg_study_tasks_updated_at on public.study_tasks;
create trigger trg_study_tasks_updated_at
before update on public.study_tasks
for each row execute function public.set_updated_at();

drop trigger if exists trg_quiz_scores_updated_at on public.quiz_scores;
create trigger trg_quiz_scores_updated_at
before update on public.quiz_scores
for each row execute function public.set_updated_at();

drop trigger if exists trg_weak_topics_updated_at on public.weak_topics;
create trigger trg_weak_topics_updated_at
before update on public.weak_topics
for each row execute function public.set_updated_at();

alter table public.student_profiles enable row level security;
alter table public.courses enable row level security;
alter table public.exams enable row level security;
alter table public.study_tasks enable row level security;
alter table public.quiz_scores enable row level security;
alter table public.weak_topics enable row level security;

drop policy if exists "Students can manage own profile" on public.student_profiles;
create policy "Students can manage own profile"
on public.student_profiles
for all
to authenticated
using (email = auth.jwt() ->> 'email')
with check (email = auth.jwt() ->> 'email');

drop policy if exists "Students can manage own courses" on public.courses;
create policy "Students can manage own courses"
on public.courses
for all
to authenticated
using (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = courses.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
)
with check (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = courses.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
);

drop policy if exists "Students can manage own exams" on public.exams;
create policy "Students can manage own exams"
on public.exams
for all
to authenticated
using (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = exams.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
)
with check (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = exams.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
);

drop policy if exists "Students can manage own study tasks" on public.study_tasks;
create policy "Students can manage own study tasks"
on public.study_tasks
for all
to authenticated
using (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = study_tasks.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
)
with check (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = study_tasks.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
);

drop policy if exists "Students can manage own quiz scores" on public.quiz_scores;
create policy "Students can manage own quiz scores"
on public.quiz_scores
for all
to authenticated
using (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = quiz_scores.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
)
with check (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = quiz_scores.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
);

drop policy if exists "Students can manage own weak topics" on public.weak_topics;
create policy "Students can manage own weak topics"
on public.weak_topics
for all
to authenticated
using (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = weak_topics.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
)
with check (
    exists (
        select 1
        from public.student_profiles sp
        where sp.id = weak_topics.student_id
          and sp.email = auth.jwt() ->> 'email'
    )
);
