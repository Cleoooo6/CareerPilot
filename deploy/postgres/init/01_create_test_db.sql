-- 创建独立测试数据库；仅用于本地/CI 集成测试。
SELECT 'CREATE DATABASE careerpilot_test OWNER careerpilot'
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'careerpilot_test'
)\gexec