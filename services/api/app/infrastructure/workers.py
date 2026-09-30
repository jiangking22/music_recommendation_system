import asyncio
from collections.abc import Callable
from weakref import WeakKeyDictionary

_worker_slots = WeakKeyDictionary()


async def run_blocking(operation: Callable):
    """At most four synchronous jobs per event loop, including timed-out jobs.

    Shielded jobs retain their slot until the actual operation finishes. They use
    their own sessions, so request cancellation never closes an in-use session.
    """
    loop = asyncio.get_running_loop()
    slots = _worker_slots.setdefault(loop, asyncio.Semaphore(4))
    await slots.acquire()
    task = asyncio.create_task(asyncio.to_thread(operation))

    def completed(job):
        slots.release()
        if not job.cancelled():
            job.exception()

    task.add_done_callback(completed)
    return await asyncio.shield(task)
