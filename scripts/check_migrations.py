import os
import sys
from sqlalchemy import create_engine, text


def main():
    raw = os.getenv("EXPECTED_TABLE_COUNT", "")
    try:
        expected = int(raw)
    except ValueError:
        expected = 0
    if expected <= 0:
        # A missing/zero expectation must fail loudly, never run as a vacuous check that
        # prints OK over a partial migration (Standard 4 / Standard 7).
        print(f"MIGRATION CHECK FAILED: EXPECTED_TABLE_COUNT must be a positive integer "
              f"(got {raw!r}); refusing to run a vacuous table-count check", file=sys.stderr)
        sys.exit(1)
    url = os.environ["DATABASE_URL"]
    with create_engine(url).connect() as c:
        n = c.execute(
            text("select count(*) from information_schema.tables where table_schema='public'")
        ).scalar_one()
    if n != expected:
        print(f"MIGRATION CHECK FAILED: expected {expected} tables, found {n}", file=sys.stderr)
        sys.exit(1)
    print(f"MIGRATION OK: {n} tables")


if __name__ == "__main__":
    main()
