"""
signalscout initdb            create tables
signalscout crawl [names...]  run spiders (all by default)
signalscout process           extract -> resolve -> enrich -> score new articles
signalscout run               crawl + process, recorded as a pipeline run
signalscout rescore           recompute scores after changing the ICP
signalscout export            write the dataset to /data (CSV + JSON)
"""

import argparse
import logging
import os
import subprocess
import sys


def crawl(names: list[str] | None = None) -> None:
    from scrapy.crawler import CrawlerProcess
    from scrapy.settings import Settings

    from signalscout.scraper.spiders.sources import ALL_SPIDERS

    settings = Settings()
    settings.setmodule("signalscout.scraper.settings", priority="project")
    process = CrawlerProcess(settings)
    for spider in ALL_SPIDERS:
        if not names or spider.name in names:
            process.crawl(spider)
    process.start()


def crawl_subprocess(run_id: int | None = None) -> int:
    """Twisted's reactor can't restart in-process, so pipeline runs crawl in a child process."""
    env = {**os.environ, "SIGNALSCOUT_RUN_ID": str(run_id or "")}
    return subprocess.call([sys.executable, "-m", "signalscout.cli", "crawl"], env=env)


def main() -> None:
    parser = argparse.ArgumentParser(prog="signalscout")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("initdb")
    c = sub.add_parser("crawl")
    c.add_argument("names", nargs="*")
    sub.add_parser("process")
    sub.add_parser("run")
    sub.add_parser("rescore")
    sub.add_parser("export")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from signalscout.db import init_db

    init_db()
    if args.cmd == "crawl":
        crawl(args.names)
    elif args.cmd == "process":
        from signalscout.pipeline.orchestrator import process_new

        print(process_new())
    elif args.cmd == "run":
        from signalscout.pipeline.orchestrator import run_pipeline

        print(run_pipeline())
    elif args.cmd == "rescore":
        from signalscout.pipeline.orchestrator import rescore_all

        print(rescore_all())
    elif args.cmd == "export":
        from signalscout.export import export_dataset

        print(export_dataset())


if __name__ == "__main__":
    main()
