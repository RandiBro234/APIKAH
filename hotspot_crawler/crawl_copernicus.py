"""Stable CLI entrypoint; implementation lives in `apikah_crawler`."""
from apikah_crawler.crawl_copernicus import main


if __name__ == "__main__":
    raise SystemExit(main())
