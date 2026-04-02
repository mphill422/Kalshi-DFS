-- DFS Tier Optimizer: Supabase Schema
-- Run this in your Supabase SQL editor

-- Lineup saves
CREATE TABLE IF NOT EXISTS dfs_lineups (
    id              BIGSERIAL PRIMARY KEY,
    contest_date    DATE NOT NULL,
    sport           TEXT DEFAULT 'NBA',
    contest_type    TEXT DEFAULT 'TIER',
    tier_1          TEXT,
    tier_2          TEXT,
    tier_3          TEXT,
    tier_4          TEXT,
    tier_5          TEXT,
    tier_6          TEXT,
    total_proj      NUMERIC(6,2),
    result_pts      NUMERIC(6,2),   -- fill in after contest
    result_rank     INTEGER,         -- your finish rank
    result_pnl      NUMERIC(8,2),   -- profit/loss
    notes           TEXT,
    saved_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast date queries
CREATE INDEX IF NOT EXISTS idx_dfs_lineups_date ON dfs_lineups(contest_date DESC);

-- Player scoring log (optional, for tracking model accuracy)
CREATE TABLE IF NOT EXISTS dfs_player_scores (
    id              BIGSERIAL PRIMARY KEY,
    contest_date    DATE NOT NULL,
    player_name     TEXT NOT NULL,
    team            TEXT,
    tier            INTEGER,
    model_score     NUMERIC(5,1),
    dk_projection   NUMERIC(5,1),
    actual_pts      NUMERIC(5,1),   -- fill in after game
    was_picked      BOOLEAN DEFAULT FALSE,
    saved_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dfs_player_date ON dfs_player_scores(contest_date DESC, player_name);
