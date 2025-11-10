/* ============
   USERS & AUTH
   ============ */

CREATE TABLE IF NOT EXISTS users (
    id               BIGSERIAL PRIMARY KEY,
    email            VARCHAR(255) NOT NULL UNIQUE,
    username         VARCHAR(50)  NOT NULL UNIQUE,
    password_hash    TEXT         NOT NULL,
    profile_image_url TEXT,
    opt_out_emails   BOOLEAN      NOT NULL DEFAULT FALSE,
    streak_count     INT          NOT NULL DEFAULT 0,
    longest_streak   INT          NOT NULL DEFAULT 0,
    last_login_at    TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_auth_providers (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider         VARCHAR(50) NOT NULL,      -- 'password', 'google', etc.
    provider_user_id VARCHAR(255) NOT NULL,     -- e.g. Google sub id
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_user_id)
);

/* ==================
   QUESTIONS & ANSWERS
   ================== */

/* Daily / generic questions you already have in JSON
   (you can gradually migrate them here later). */
CREATE TABLE IF NOT EXISTS daily_questions (
    id               BIGSERIAL PRIMARY KEY,
    question_text    TEXT        NOT NULL,
    ideal_answer     TEXT,
    active_for_date  DATE        NOT NULL,   -- the date this is the “daily” question
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- All answers given by users (daily + generic + job-specific)
CREATE TABLE IF NOT EXISTS answers (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question_source   VARCHAR(20) NOT NULL,   -- 'daily', 'generic', 'job'
    question_id       BIGINT,                -- ID from daily_questions / jobs / job_specific_questions
    raw_question_text TEXT        NOT NULL,  -- store the actual question text used
    answer_text       TEXT        NOT NULL,
    is_voice          BOOLEAN     NOT NULL DEFAULT FALSE,
    transcript        TEXT,
    relevance_score   NUMERIC(5,2),
    confidence_score  NUMERIC(5,2),
    final_score       NUMERIC(5,2),
    feedback_text     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_answers_user_created
    ON answers (user_id, created_at DESC);

/* ===============
   JOBS & JOB Qs
   =============== */

CREATE TABLE IF NOT EXISTS jobs (
    id          BIGSERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    category    VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_specific_questions (
    id           BIGSERIAL PRIMARY KEY,
    job_id       BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    question_text TEXT  NOT NULL,
    ideal_answer  TEXT,
    tags          TEXT[],               -- ['ownership', 'leadership'] etc.
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_questions_job
    ON job_specific_questions (job_id);

/* =====================
   CUSTOM PREP REPORTS
   ===================== */

CREATE TABLE IF NOT EXISTS prep_reports (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id) ON DELETE SET NULL,
    job_title       VARCHAR(255) NOT NULL,
    company_name    VARCHAR(255),
    job_description TEXT,
    resume_text     TEXT,
    report_json     JSONB       NOT NULL,   -- full GPT report
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prep_reports_user_created
    ON prep_reports (user_id, created_at DESC);

/* ==========
   COURSES
   ========== */

CREATE TABLE IF NOT EXISTS courses (
    id          BIGSERIAL PRIMARY KEY,
    slug        VARCHAR(100) NOT NULL UNIQUE,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    level       VARCHAR(50),   -- 'beginner', 'intermediate', etc.
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS course_lessons (
    id          BIGSERIAL PRIMARY KEY,
    course_id   BIGINT      NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    content_md  TEXT,              -- markdown content
    sort_order  INT         NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_course_lessons_course_order
    ON course_lessons (course_id, sort_order);

CREATE TABLE IF NOT EXISTS course_quizzes (
    id            BIGSERIAL PRIMARY KEY,
    course_id     BIGINT      NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    question_text TEXT        NOT NULL,
    correct_answer TEXT,
    wrong_answers  TEXT[],          -- array of wrong options
    sort_order    INT         NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_course_quizzes_course_order
    ON course_quizzes (course_id, sort_order);

/* ==========
   BADGES
   ========== */

CREATE TABLE IF NOT EXISTS badges (
    id          BIGSERIAL PRIMARY KEY,
    code        VARCHAR(100) NOT NULL UNIQUE,  -- e.g. 'DAILY_STREAK_7'
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_badges (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_id    BIGINT NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
    awarded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, badge_id)
);

/* ================
   STREAKS & WINNERS
   ================ */

CREATE TABLE IF NOT EXISTS streak_history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date        DATE   NOT NULL,
    status      VARCHAR(20) NOT NULL,  -- 'kept', 'broken'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, date)
);

CREATE TABLE IF NOT EXISTS winners (
    id            BIGSERIAL PRIMARY KEY,
    winner_date   DATE   NOT NULL,           -- the date of the daily question
    user_id       BIGINT REFERENCES users(id) ON DELETE SET NULL,
    question_text TEXT   NOT NULL,
    answer_text   TEXT   NOT NULL,
    final_score   NUMERIC(5,2),
    feedback_text TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (winner_date)
);

ALTER TABLE users
ADD COLUMN IF NOT EXISTS opt_out_emails BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW();

