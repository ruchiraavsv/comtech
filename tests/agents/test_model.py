import json
from types import SimpleNamespace

import pytest

from comtech.agents.budget import TokenCounter
from comtech.agents.contracts import Decision
from comtech.agents.model import StructuredModel
from comtech.research.contracts import SupervisorTurn
from comtech.settings import Settings


class Responses:
    def __init__(self, *, refused=False):
        self.requests = []
        self.refused = refused

    async def parse(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            status="completed",
            usage=None,
            output_parsed=None if self.refused else Decision(action="finalize"),
        )


@pytest.mark.parametrize(
    "code", ["credit_balance_exhausted", "insufficient_quota", "rate_limit_exceeded"]
)
async def test_quota_exhaustion_is_not_retried_as_a_transient_rate_limit(code):
    import httpx
    from openai import RateLimitError

    from comtech.agents.errors import ProviderQuotaExhausted
    from comtech.agents.model import MODEL_RETRY

    class FailedResponse:
        async def parse(self, **kwargs):
            raise RateLimitError(
                "Synthetic provider refusal",
                response=httpx.Response(429, request=httpx.Request("POST", "https://example.test")),
                body={"code": code},
            )

    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=FailedResponse()),
    )
    expected = RateLimitError if code == "rate_limit_exceeded" else ProviderQuotaExhausted
    with pytest.raises(expected) as error:
        await model.generate("decision", {}, Decision, 1000)
    assert isinstance(error.value, MODEL_RETRY.retry_on) == (code == "rate_limit_exceeded")


async def test_role_and_complexity_model_selection_and_limits():
    responses = Responses()
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=responses),
    )
    assert model.selection("plan", {}) == ("gpt-6-sol", "low")
    assert model.selection("review", {}) == ("gpt-6-sol", "medium")
    assert model.selection("decision", {"task": {"complexity": "simple"}}) == ("gpt-6-luna", "none")
    assert model.selection("decision", {"task": {"complexity": "complex"}}) == ("gpt-6-sol", "low")
    assert model.selection("final", {}) == ("gpt-6-luna", "none")
    await model.generate("decision", {"task": {}}, Decision, 1000)
    assert responses.requests[0]["max_output_tokens"] == 1000
    assert not responses.requests[0]["store"]


async def test_model_refusal_is_execution_failure_not_semantic_answer():
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=Responses(refused=True)),
    )
    with pytest.raises(RuntimeError, match="refused"):
        await model.generate("decision", {}, Decision, 1000)


class ToolResponses:
    def __init__(self, output, status="completed"):
        self.output, self.status, self.requests = output, status, []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(status=self.status, output=self.output, usage=None)


def tool_call(name="knowledge_worker", task_id="k"):
    from comtech.agents.contracts import KnowledgeTask
    from comtech.agents.model import KnowledgeToolArguments

    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=KnowledgeToolArguments(
            resolved_request="Owner?",
            task=KnowledgeTask(task_id=task_id, objective="Find owner"),
        ).model_dump_json(),
    )


async def test_supervisor_uses_native_tools_and_only_advertises_available_capabilities():
    responses = ToolResponses([tool_call(), tool_call(task_id="second")])
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=responses),
    )
    value, _ = await model.generate(
        "supervisor",
        {"available_specialists": ["knowledge_worker"]},
        SupervisorTurn,
        2000,
    )
    assert len(value.decision.calls) == 2
    request = responses.requests[0]
    assert {t["name"] for t in request["tools"]} == {"knowledge_worker", "submit_answer"}
    assert all(t["strict"] for t in request["tools"])
    assert request["tool_choice"] == "required" and not request["store"]
    with pytest.raises(RuntimeError, match="advertised"):
        await model.generate("supervisor", {"available_specialists": []}, SupervisorTurn, 2000)
    assert [t["name"] for t in responses.requests[-1]["tools"]] == ["submit_answer"]


@pytest.mark.parametrize(
    "output,status",
    [
        ([], "completed"),
        ([tool_call()], "incomplete"),
        ([tool_call("research")], "completed"),
        ([tool_call(), tool_call("submit_answer")], "completed"),
    ],
)
async def test_supervisor_rejects_refusals_unknown_tools_and_mixed_submission(output, status):
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=ToolResponses(output, status)),
    )
    with pytest.raises((RuntimeError, ValueError)):
        await model.generate(
            "supervisor",
            {"available_specialists": ["knowledge_worker"]},
            SupervisorTurn,
            2000,
        )


async def test_incomplete_supervisor_output_returns_compact_submission_feedback():
    from comtech.agents.errors import InvalidModelOutput

    responses = ToolResponses([tool_call()], status="incomplete")
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=responses),
    )
    with pytest.raises(InvalidModelOutput, match="compact package"):
        await model.generate(
            "supervisor", {"available_specialists": ["knowledge_worker"]}, SupervisorTurn, 2000
        )


async def test_research_native_tools_use_shared_shapes_and_validate_untrusted_arguments():
    from comtech.research.actions import ResearchTurn
    from comtech.retrieval.tools import DOCUMENT_SCHEMAS

    responses = ToolResponses(
        [
            SimpleNamespace(
                type="function_call", name="knowledge_search", arguments='{"query":"commit"}'
            )
        ]
    )
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=responses),
    )
    payload = {"tools": DOCUMENT_SCHEMAS, "python_available": False}
    result, _ = await model.generate("research", payload, ResearchTurn, 2000)
    assert result.decision.arguments.query == "commit"
    request = responses.requests[0]
    tools = {t["name"]: t for t in request["tools"]}
    assert set(tools) == {"knowledge_search", "read_document_sections", "delegate", "finalize"}
    assert (
        tools["knowledge_search"]["parameters"]
        == DOCUMENT_SCHEMAS["knowledge_search"]["parameters"]
    )
    assert not request["parallel_tool_calls"] and not request["store"]
    assert model.selection("research", {}) == model.selection("research_finalize", {})
    responses.output[0].arguments = '{"query":"commit","url":"https://invalid.example"}'
    with pytest.raises(ValueError):
        await model.generate("research", payload, ResearchTurn, 2000)
    responses.output[0].name = "execute_python"
    with pytest.raises(RuntimeError, match="advertised"):
        await model.generate("research", payload, ResearchTurn, 2000)


@pytest.mark.parametrize("maximum", [1, 3, 5])
async def test_native_research_tools_preserve_configured_reader_limit(maximum):
    from comtech.agents.contracts import Limits
    from comtech.agents.model import research_tools
    from comtech.research.actions import ResearchTurn
    from comtech.retrieval.tools import document_schemas

    advertised = document_schemas(Limits(max_sections_per_read=maximum))
    native = {t["name"]: t for t in research_tools({"tools": advertised})}
    args = native["read_document_sections"]["parameters"]["properties"]
    assert args["max_sections"]["maximum"] == maximum
    assert args["max_sections"]["default"] <= maximum
    assert advertised == document_schemas(Limits(max_sections_per_read=maximum))
    responses = ToolResponses(
        [
            SimpleNamespace(
                type="function_call",
                name="read_document_sections",
                arguments='{"document_id":"DOC-0","query":"transition"}',
            )
        ]
    )
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=responses),
    )
    value, _ = await model.generate("research", {"tools": advertised}, ResearchTurn, 2000)
    assert value.decision.arguments.max_sections == min(3, maximum)
    request = responses.requests[0]
    assert "tools" not in json.loads(request["input"])
    reader = next(tool for tool in request["tools"] if tool["name"] == "read_document_sections")
    assert reader["parameters"]["properties"]["max_sections"]["maximum"] == maximum


async def test_parallel_request_mismatch_is_recoverable_without_executing_calls():
    from comtech.agents.errors import InvalidModelOutput

    first, second = tool_call(), tool_call(task_id="second")
    second.arguments = second.arguments.replace("Owner?", "Find dependencies?")
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=ToolResponses([first, second])),
    )
    with pytest.raises(InvalidModelOutput, match="same complete resolved_request"):
        await model.generate(
            "supervisor", {"available_specialists": ["knowledge_worker"]}, SupervisorTurn, 2000
        )


async def test_malformed_provider_json_is_recoverable_and_feedback_excludes_raw_input():
    from comtech.agents.errors import InvalidModelOutput
    from comtech.research.actions import ResearchTurn

    responses = ToolResponses(
        [SimpleNamespace(type="function_call", name="finalize", arguments="{} private-trailing")]
    )
    model = StructuredModel(
        Settings(_env_file=None, openai_api_key="test"),
        TokenCounter(),
        SimpleNamespace(responses=responses),
    )
    with pytest.raises(InvalidModelOutput) as error:
        await model.generate("research", {}, ResearchTurn, 2000)
    assert "private-trailing" not in str(error.value)
