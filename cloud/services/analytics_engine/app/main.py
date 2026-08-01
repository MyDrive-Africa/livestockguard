"""
LivestockGuard Analytics Engine — Self-Monitoring, Learning & Reporting

Runs scheduled analysis jobs on accumulated BLE sighting and position data:
- Baseline builder: learns normal behaviour patterns per animal
- Anomaly detector: flags deviations from baselines
- Suggestion engine: converts anomalies into actionable recommendations
- Report generator: compiles daily/weekly intelligence reports for farm admin
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app import config
from app.jobs.baseline_builder import run_baseline_builder
from app.jobs.anomaly_detector import run_anomaly_detector
from app.jobs.suggestion_engine import run_suggestion_engine
from app.jobs.report_generator import run_report_generator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("analytics_engine")


async def run_full_analysis():
    """Run all jobs in sequence (used for startup and manual triggers)."""
    logger.info("Running full analysis pipeline...")
    try:
        await run_baseline_builder()
        await run_anomaly_detector()
        await run_suggestion_engine()
        await run_report_generator()
        logger.info("Full analysis pipeline complete.")
    except Exception as e:
        logger.error(f"Analysis pipeline error: {e}", exc_info=True)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the job scheduler."""
    scheduler = AsyncIOScheduler(timezone="Africa/Johannesburg")

    # Nightly baseline computation (02:00 SAST)
    scheduler.add_job(
        run_baseline_builder,
        CronTrigger(hour=config.BASELINE_CRON_HOUR, minute=0),
        id="baseline_builder",
        name="Baseline Builder (nightly)",
        replace_existing=True,
    )

    # Anomaly detection every N hours
    scheduler.add_job(
        run_anomaly_detector,
        IntervalTrigger(hours=config.ANOMALY_CHECK_INTERVAL_HOURS),
        id="anomaly_detector",
        name="Anomaly Detector",
        replace_existing=True,
    )

    # Suggestion engine runs after anomaly detection
    scheduler.add_job(
        run_suggestion_engine,
        IntervalTrigger(hours=config.ANOMALY_CHECK_INTERVAL_HOURS, minutes=5),
        id="suggestion_engine",
        name="Suggestion Engine",
        replace_existing=True,
    )

    # Daily report (18:00 SAST)
    scheduler.add_job(
        run_report_generator,
        CronTrigger(hour=config.DAILY_REPORT_HOUR, minute=0),
        id="daily_report",
        name="Daily Report Generator",
        replace_existing=True,
    )

    # Weekly report (Sunday 19:00 SAST)
    scheduler.add_job(
        run_report_generator,
        CronTrigger(day_of_week=config.WEEKLY_REPORT_DAY, hour=config.WEEKLY_REPORT_HOUR, minute=0),
        id="weekly_report",
        name="Weekly Report Generator",
        replace_existing=True,
    )

    return scheduler


async def main():
    """Entry point for the analytics engine service."""
    logger.info("=" * 60)
    logger.info(" LivestockGuard Analytics Engine v1.0")
    logger.info(f" Started: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f" Baseline window: {config.BASELINE_WINDOW_DAYS} days")
    logger.info(f" Anomaly check: every {config.ANOMALY_CHECK_INTERVAL_HOURS}h")
    logger.info(f" Daily report: {config.DAILY_REPORT_HOUR}:00 SAST")
    logger.info(f" Run on startup: {config.RUN_ON_STARTUP}")
    logger.info("=" * 60)

    scheduler = create_scheduler()
    scheduler.start()

    # Run immediately on startup if configured (useful for dev/demo)
    if config.RUN_ON_STARTUP:
        logger.info("Running initial analysis on startup...")
        await run_full_analysis()

    # Keep alive until signal
    stop_event = asyncio.Event()

    def shutdown(sig, frame):
        logger.info(f"Received {sig}, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown(wait=False)
        logger.info("Analytics engine stopped.")


if __name__ == "__main__":
    asyncio.run(main())
