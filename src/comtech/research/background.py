"""Ordinary reviewed graph handler, independent of HTTP/SSE lifetime."""

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from comtech.events import graph_events

from .queue import bounded
from .registry import validate_checkpoint_identity
from .scheduler import Outcome


class BackgroundGraph:
    def __init__(self, graph, delivery, pinned_versions=None, research=None):
        self.graph, self.delivery = graph, delivery
        self.pinned_versions = pinned_versions
        self.research = research

    async def __call__(self, claim):
        objective = claim.objective
        if (
            self.pinned_versions is not None
            and objective["pinned_versions"] != self.pinned_versions
        ):
            raise ValueError("Pinned sources are unavailable")
        run_id, thread_id = objective["run_id"], objective["thread_id"]
        config = {
            "configurable": {
                "thread_id": str(thread_id),
                "app_run_id": str(run_id),
                "objective_id": str(objective["id"]),
            },
            "recursion_limit": 200,
        }
        inputs = {"messages": [HumanMessage(content=claim.task["input"]["message"])]}
        if claim.task["continuation"].get("recover") or claim.task["continuation"].get(
            "research_wait"
        ):
            prior = await self.graph.aget_state(config)
            if str(prior.values.get("run_id")) == str(run_id):
                validate_checkpoint_identity(
                    prior,
                    {"thread_id": thread_id, "graph_run_id": run_id, "graph_version": 2},
                    objective["id"],
                )
                if not prior.next:
                    return await self.result(prior)
                config["configurable"]["checkpoint_id"] = prior.config["configurable"][
                    "checkpoint_id"
                ]
                inputs = None
                if any(t.interrupts for t in prior.tasks):
                    inputs = Command(resume=True)
            elif prior.next:
                raise ValueError("Pending checkpoint belongs to another canonical run")
        final_seen = False
        async for number, event in enumerate_events(
            graph_events(self.graph, inputs, config, run_id, thread_id)
        ):
            if event.type == "TEXT_MESSAGE_CONTENT":
                final_seen = True
            elif event.type in ("RUN_STARTED", "STEP_STARTED", "STEP_FINISHED", "CUSTOM"):
                if event.type == "CUSTOM" and event.name != "agent.activity":
                    continue
                key = (
                    "started"
                    if event.type == "RUN_STARTED"
                    else f"{claim.lease.attempt_id}:{number}"
                )
                await self.delivery.progress(claim.lease, key, event)
        latest_config = {**config, "configurable": dict(config["configurable"])}
        latest_config["configurable"].pop("checkpoint_id", None)
        snapshot = await self.graph.aget_state(latest_config)
        validate_checkpoint_identity(
            snapshot,
            {"thread_id": thread_id, "graph_run_id": run_id, "graph_version": 2},
            objective["id"],
        )
        waits = [
            i.value["research_wait"]
            for t in snapshot.tasks
            for i in t.interrupts
            if isinstance(i.value, dict) and "research_wait" in i.value
        ]
        if waits:
            return Outcome(
                state="waiting_children",
                dependencies=tuple(sorted({child for wait in waits for child in wait})),
                continuation={"research_wait": True},
            )
        if not final_seen:
            raise ValueError("Graph did not produce a final answer")
        return await self.result(snapshot)

    async def result(self, snapshot):
        state = snapshot.values
        if (
            snapshot.next
            or not state.get("final_answer")
            or state.get("review_decision", {}).get("status") != "approved"
            or state.get("validation_errors")
        ):
            raise ValueError("Graph did not finish with a reviewed answer")
        selected = {ref for c in state["answer_package"]["claims"] for ref in c["evidence_ids"]}
        retained = await self.research.retain(state) if self.research else {}
        result = bounded(
            {
                "answer": state["final_answer"],
                "review_status": "approved",
                "answer_package": state["answer_package"],
                "evidence": {k: state["evidence"][k] for k in selected},
                "research": retained,
            }
        )
        return Outcome(result=result)


async def enumerate_events(events):
    number = 0
    async for event in events:
        yield number, event
        number += 1
