import asyncio
from core.orchestrator import TaskOrchestrator, TaskPlan, TaskStep

def test_retries_then_succeeds():
    calls = {"n": 0}

    async def execute(step):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("temporary failure")
        return "done"

    async def verify(step, value):
        return value == "done"

    async def run():
        engine = TaskOrchestrator(execute, verifier=verify)
        return await engine.run(TaskPlan(
            goal="test recovery",
            steps=[TaskStep(id="one", description="recover", retries=2)]
        ))

    result = asyncio.run(run())
    assert result.ok is True
    assert calls["n"] == 3

def test_verification_failure_is_not_reported_as_success():
    async def execute(step):
        return "returned but not complete"

    async def verify(step, value):
        return False

    async def run():
        engine = TaskOrchestrator(execute, verifier=verify)
        return await engine.run(TaskPlan(
            goal="test verification",
            steps=[TaskStep(id="one", description="verify", retries=1)]
        ))

    result = asyncio.run(run())
    assert result.ok is False
    assert result.failed == ["one"]
