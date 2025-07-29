CREATE TABLE IF NOT EXISTS code_jobs (
    id SERIAL PRIMARY KEY,
    language VARCHAR(16) NOT NULL,
    code TEXT NOT NULL,
    stdin TEXT,
    status VARCHAR(16) DEFAULT 'pending',
    result_stdout TEXT,
    result_stderr TEXT,
    result_exit_code INTEGER,
    result_time INTEGER
);
