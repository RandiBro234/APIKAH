"""Stable CLI entrypoint; implementation lives in `apikah_crawler`."""
from apikah_crawler.build_training_table import main


if __name__ == "__main__":
    raise SystemExit(main())
