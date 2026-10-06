"""JARVIS 2.0 task orchestration core.

Framework-agnostic execution engine for planning, retries, verification and
authorization. It deliberately does not execute arbitrary code itself; the
existing action/plugin registries remain the authority for real side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import monotonic
from typing import Any, Awaitable, Callable, Mapping, Sequence


class Authorization(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    BLOCK = "block"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    id: str
    description: str
    action: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    authorization: Authorization = Authorization.AUTO
    retries: int = 2
    verify: bool = True
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    attempts: int = 0


@dataclass
class TaskPlan:
    goal: str
    steps: list[TaskStep]
    task_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    ok: bool
    result: Any = None
    error: str | None = None
    verified: bool = False


@dataclass
class TaskResult:
    ok: bool
    goal: str
    completed: list[str]
    failed: list[str]
    results: dict[str, Any]
    error: str | None = None
    elapsed_seconds: float = 0.0


Executor = Callable[[TaskStep], Awaitable[Any]]
Verifier = Callable[[TaskStep, Any], Awaitable[bool]]
Confirmer = Callable[[TaskStep], Awaitable[bool]]
Progress = Callable[[TaskPlan, TaskStep], Awaitable[None]]


class TaskOrchestrator:
    """Run a plan with bounded recovery and honest verification.

    Design rule: ordinary failures trigger recovery; authorization boundaries
    still matter. The engine never converts a failed/unverified action into
    success merely to satisfy the conversation.
    """

    def __init__(
        self,
        executor: Executor,
        *,
        verifier: Verifier | None = None,
        confirmer: Confirmer | None = None,
        progress: Progress | None = None,
        max_task_seconds: float = 900.0,
    ) -> None:
        self.executor = executor
        self.verifier = verifier
        self.confirmer = confirmer
        self.progress = progress
        self.max_task_seconds = max_task_seconds

    async def run(self, plan: TaskPlan) -> TaskResult:
        started = monotonic()
        completed: list[str] = []
        failed: list[str] = []
        results: dict[str, Any] = {}

        for step in plan.steps:
            if monotonic() - started > self.max_task_seconds:
                step.status = StepStatus.FAILED
                step.error = "Task time limit reached."
                failed.append(step.id)
                break

            if step.authorization is Authorization.BLOCK:
                step.status = StepStatus.SKIPPED
                step.error = "Action is blocked by the authorization policy."
                failed.append(step.id)
                continue

            if step.authorization is Authorization.CONFIRM:
                if self.confirmer is None or not await self.confirmer(step):
                    step.status = StepStatus.SKIPPED
                    step.error = "User confirmation was not granted."
                    failed.append(step.id)
                    continue

            step.status = StepStatus.RUNNING
            if self.progress:
                await self.progress(plan, step)

            last_error: str | None = None
            for attempt in range(max(0, step.retries) + 1):
                step.attempts = attempt + 1
                try:
                    value = await self.executor(step)
                    if step.verify and self.verifier is not None:
                        verified = await self.verifier(step, value)
                    else:
                        verified = True

                    if not verified:
                        raise RuntimeError("Action returned, but verification failed.")

                    step.result = value
                    step.status = StepStatus.SUCCEEDED
                    step.error = None
                    results[step.id] = value
                    completed.append(step.id)
                    break
                except Exception as exc:  # recovery is intentionally bounded
                    last_error = str(exc)
                    if attempt < step.retries:
                        continue

            else:
                step.status = StepStatus.FAILED
                step.error = last_error or "Unknown execution failure."
                failed.append(step.id)

            if self.progress:
                await self.progress(plan, step)

            # Do not silently continue after a failed dependency.
            if step.status is StepStatus.FAILED:
                break

        elapsed = monotonic() - started
        ok = bool(plan.steps) and not failed and all(
            s.status is StepStatus.SUCCEEDED for s in plan.steps
        )
        return TaskResult(
            ok=ok,
            goal=plan.goal,
            completed=completed,
            failed=failed,
            results=results,
            error=None if ok else next(
                (s.error for s in plan.steps if s.error), "Task did not complete."
            ),
            elapsed_seconds=elapsed,
        )


def classify_authorization(
    action: str,
    args: Mapping[str, Any] | None = None,
    *,
    sensitive_actions: Sequence[str] = (),
    blocked_actions: Sequence[str] = (),
) -> Authorization:
    """Classify an action without pretending every tool is equally safe."""
    name = action.strip().lower()
    if name in {x.strip().lower() for x in blocked_actions}:
        return Authorization.BLOCK
    if name in {x.strip().lower() for x in sensitive_actions}:
        return Authorization.CONFIRM

    data = {str(k).lower(): v for k, v in (args or {}).items()}
    if any(key in data for key in ("password", "private_key", "secret")):
        return Authorization.CONFIRM
    return Authorization.AUTO
