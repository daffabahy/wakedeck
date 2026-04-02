import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")

def add_schedule_job(schedule_id: int, cron_expr: str, callback_func):
    job_id = f"job_schedule_{schedule_id}"
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler.add_job(
            callback_func,
            trigger=trigger,
            id=job_id,
            args=[schedule_id],
            replace_existing=True
        )
        logger.info(f"Added job {job_id} with cron {cron_expr}")
        return True
    except Exception as e:
        logger.error(f"Failed to add job {job_id}: {e}")
        return False

def remove_schedule_job(schedule_id: int):
    job_id = f"job_schedule_{schedule_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Removed job {job_id}")

def get_next_run_time(schedule_id: int):
    job_id = f"job_schedule_{schedule_id}"
    job = scheduler.get_job(job_id)
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
