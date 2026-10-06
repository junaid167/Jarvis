"""Long-running task manager for JARVIS 2.0."""
from __future__ import annotations
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Any

@dataclass
class BackgroundTask:
    task_id: str
    goal: str
    created_at: str
    status: str = "queued"
    progress: str = ""
    result: Any = None
    error: str | None = None
    _task: asyncio.Task | None = field(default=None, repr=False)

class TaskManager:
    def __init__(self, max_concurrent: int = 3):
        self._tasks: dict[str, BackgroundTask] = {}
        self._sem = asyncio.Semaphore(max_concurrent)

    @property
    def tasks(self):
        return dict(self._tasks)

    async def start(self, goal: str, worker: Callable[[BackgroundTask], Awaitable[Any]]) -> str:
        task_id = uuid.uuid4().hex[:10]
        record = BackgroundTask(task_id, goal, datetime.now(timezone.utc).isoformat())
        self._tasks[task_id] = record
        record._task = asyncio.create_task(self._run(record, worker))
        return task_id

    async def _run(self, record, worker):
        async with self._sem:
            record.status = "running"
            try:
                record.result = await worker(record)
                record.status = "completed"
            except asyncio.CancelledError:
                record.status = "cancelled"
                raise
            except Exception as exc:
                record.status = "failed"
                record.error = str(exc)

    def update_progress(self, task_id: str, message: str) -> None:
        record = self._tasks.get(task_id)
        if record:
            record.progress = str(message)

    async def cancel(self, task_id: str) -> bool:
        record = self._tasks.get(task_id)
        if not record or not record._task or record._task.done():
            return False
        record._task.cancel()
        return True

    def status(self, task_id: str | None = None):
        return self._tasks.get(task_id) if task_id else list(self._tasks.values())

    async def shutdown(self) -> None:
        running = [r._task for r in self._tasks.values() if r._task and not r._task.done()]
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
