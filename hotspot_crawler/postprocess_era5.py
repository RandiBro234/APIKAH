"""Stable CLI entrypoint; implementation lives in `apikah_crawler`."""
from apikah_crawler.postprocess_era5 import main


if __name__ == "__main__":
    raise SystemExit(main())
