"""Stable CLI entrypoint for verified local data migration."""
from apikah_crawler.migrate_data_layout import main


if __name__ == "__main__":
    raise SystemExit(main())
