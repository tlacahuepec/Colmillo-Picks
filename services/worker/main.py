from __future__ import annotations

import time

from services.api import jobs
from services.api.main import _execute_pipeline_job


def run_worker_loop(poll_seconds: float = 0.5) -> None:
    while True:
        item = jobs.dequeue_pick_run()
        if item is None:
            time.sleep(poll_seconds)
            continue
        pick_id, request_dict, bundle_kwargs, job_id = item
        try:
            success = _execute_pipeline_job(
                pick_id=pick_id,
                request_dict=request_dict,
                bundle_kwargs=bundle_kwargs,
            )
            if success:
                jobs.mark_job_done(job_id)
            else:
                jobs.mark_job_failed(job_id, "pipeline execution failed")
        except Exception as exc:  # defensive guard
            jobs.mark_job_failed(job_id, str(exc))


if __name__ == "__main__":
    run_worker_loop()
