"""Guarded reset/snapshot utility for the isolated E2E database."""

import json
import os
import sys

import psycopg

TEST_DB = "careerpilot_test"
TABLES = (
    "roadmap_task, roadmap_stage, career_roadmap, "
    "profile_revision, market_job, market_import_batch, "
    "market_source, profile_analysis, resume_parse, career_profile, "
    "agent_trace, agent_run, message, conversation, app_user"
)


def counts(cur) -> dict[str, int]:
    result: dict[str, int] = {}
    for table in (
        "app_user",
        "career_profile",
        "profile_revision",
        "career_roadmap",
        "conversation",
        "message",
        "market_source",
        "market_job",
    ):
        cur.execute(f"SELECT count(*) AS n FROM {table}")
        result[table] = cur.fetchone()[0]
    return result


def main() -> None:
    if os.environ.get("APP_ENV") != "test":
        raise SystemExit("refusing E2E reset: APP_ENV is not test")
    if os.environ.get("E2E_DB_GUARD") != TEST_DB:
        raise SystemExit("refusing E2E reset: E2E_DB_GUARD does not match")
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("refusing E2E reset: DATABASE_URL is missing")

    with psycopg.connect(url) as conn:
        if conn.info.dbname != TEST_DB:
            raise SystemExit(f"refusing E2E reset: db is {conn.info.dbname}")
        with conn.cursor() as cur:
            if "--snapshot" in sys.argv:
                print(json.dumps({"db": conn.info.dbname, "counts": counts(cur)}))
                return
            cur.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
            conn.commit()
            print(json.dumps({"db": conn.info.dbname, "counts": counts(cur)}))


if __name__ == "__main__":
    main()