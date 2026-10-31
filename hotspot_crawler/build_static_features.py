"""Stable CLI entrypoint; implementation lives in `apikah_crawler`."""
from apikah_crawler.build_static_features import main


if __name__ == "__main__":
    raise SystemExit(main())
