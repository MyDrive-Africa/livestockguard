"""
LivestockGuard Herding Orchestrator — the robotic-herdsman brain.

Runs a periodic control loop that keeps every animal inside its boundary using a
small fleet of herding robots (typically 4 per farm):

    1. SENSE      load fleet, latest animal positions, and the farm boundary
    2. EVALUATE   classify each animal SAFE / APPROACHING / BREACHED (containment)
    3. PLAN       build prioritised herding targets + intercept points (planner)
    4. ASSIGN     match robots to targets, cost-based; idle robots patrol (assigner)
    5. COMMAND    publish intent to robots over MQTT; persist jobs

Adds *actuation* to the existing sensing platform: the same breach the system would
alert a human about now also dispatches the nearest robot to push the animal back.

Follows the analytics_engine service shape: APScheduler + asyncio + signal shutdown,
config from env vars, ``python -m app.main`` entry point.
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app import config, db
from app.assigner import assign
from app.commands import CommandBridge
from app.containment import Containment
from app.planner import plan_targets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("herding_orchestrator")

# Shared handles, initialised in main().
_pool = None
_bridge: CommandBridge | None = None


async def run_control_loop() -> None:
    """One full sense -> evaluate -> plan -> assign -> command pass across all farms."""
    if config.DEFAULT_MODE == "paused":
        logger.debug("Mode is paused; skipping control loop.")
        return
    if _pool is None or _bridge is None:
        logger.warning("Control loop skipped: dependencies not ready.")
        return

    try:
        farms = await db.load_active_farms(_pool)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load active farms: %s", exc)
        return

    for farm_id in farms:
        await _run_farm(farm_id)


async def _run_farm(farm_id: str) -> None:
    """Run the control loop for a single farm."""
    boundary = await db.load_boundary(_pool, farm_id)
    if boundary is None:
        logger.debug("Farm %s has no active boundary; skipping.", farm_id[:8])
        return

    fleet = await db.load_fleet(_pool, farm_id)
    if not fleet:
        logger.debug("Farm %s has no available robots; skipping.", farm_id[:8])
        return

    animals = await db.load_recent_animals(_pool, farm_id)
    if not animals:
        logger.debug("Farm %s has no recent animal positions.", farm_id[:8])
        return

    # 2. EVALUATE containment for every animal.
    results = {a.animal_id: boundary.evaluate(a.lat, a.lon) for a in animals}
    breached = sum(1 for r in results.values() if r.state == Containment.BREACHED)
    approaching = sum(1 for r in results.values() if r.state == Containment.APPROACHING)

    # 3. PLAN herding targets.
    targets = plan_targets(
        animals, results, boundary, cluster_merge_radius_m=config.CLUSTER_MERGE_RADIUS_M
    )

    # 4. ASSIGN robots to targets.
    assignments = assign(
        fleet, targets, min_battery_for_job_pct=config.MIN_BATTERY_FOR_JOB_PCT
    )

    logger.info(
        "Farm %s: %d animals (%d breached, %d approaching), %d robots, %d targets",
        farm_id[:8], len(animals), breached, approaching, len(fleet), len(targets),
    )

    # 5. COMMAND + persist jobs for actionable assignments.
    for a in assignments:
        _bridge.send(a)
        if a.action in ("shepherd", "intercept"):
            try:
                await db.persist_job(_pool, farm_id, a.robot_id, a.action, a.target)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to persist job for robot %s: %s", a.serial, exc)


def create_scheduler() -> AsyncIOScheduler:
    """Create the control-loop scheduler."""
    scheduler = AsyncIOScheduler(timezone="Africa/Johannesburg")
    scheduler.add_job(
        run_control_loop,
        IntervalTrigger(seconds=config.LOOP_INTERVAL_SEC),
        id="herding_control_loop",
        name="Herding Control Loop",
        replace_existing=True,
        max_instances=1,          # never overlap passes
        coalesce=True,
    )
    return scheduler


async def main() -> None:
    """Entry point for the herding orchestrator service."""
    global _pool, _bridge

    logger.info("=" * 60)
    logger.info(" LivestockGuard Herding Orchestrator v1.0")
    logger.info(f" Started: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f" Mode: {config.DEFAULT_MODE}")
    logger.info(f" Loop interval: {config.LOOP_INTERVAL_SEC}s")
    logger.info(f" MQTT: {config.MQTT_HOST}:{config.MQTT_PORT}")
    logger.info("=" * 60)

    _bridge = CommandBridge()
    _bridge.connect()

    try:
        _pool = await db.connect_pool()
        logger.info("Database pool established.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to connect to database: %s", exc)
        _bridge.disconnect()
        return

    scheduler = create_scheduler()
    scheduler.start()

    if config.RUN_ON_STARTUP:
        logger.info("Running initial control loop on startup...")
        await run_control_loop()

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
        if _bridge:
            _bridge.disconnect()
        if _pool:
            await _pool.close()
        logger.info("Herding orchestrator stopped.")


if __name__ == "__main__":
    asyncio.run(main())
