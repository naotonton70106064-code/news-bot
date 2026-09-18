-- M3: pgvector 導入に伴うスキーマ変更
-- 前提: pgvector が利用可能な PostgreSQL

CREATE EXTENSION IF NOT EXISTS vector;

-- フロー(news) / ストック(case-study, blog) の区別
-- DEFAULT 'news' NOT NULL = 書き忘れても安全側に倒れる
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS content_type TEXT NOT NULL DEFAULT 'news';

-- 埋め込みベクトル(voyage-4-lite / 1024次元)
-- NULL許容 = WHERE embedding IS NULL で差分処理するため
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- HNSWインデックス
-- 名前を明示 + IF NOT EXISTS(名前なしで2回叩くと2本できるため)
CREATE INDEX IF NOT EXISTS idx_articles_embedding_hnsw
    ON articles USING hnsw (embedding vector_cosine_ops);

-- M5: 生成結果の判定を保存する
ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS judge_result JSONB;