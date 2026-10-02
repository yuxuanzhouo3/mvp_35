import time

from config.settings import Settings
from db.store import open_store

from app.workers.execute import execute_job, reclaim_stale


def main() -> None:
    settings = Settings()
    store = open_store(settings)
    while True:
        reclaim_stale(store)
        queued = store.query("jobs", filters={"status": "queued"}, limit=20)["items"]
        for job in queued:
            execute_job(store, settings, job["id"])
        time.sleep(2)


if __name__ == "__main__":
    main()
