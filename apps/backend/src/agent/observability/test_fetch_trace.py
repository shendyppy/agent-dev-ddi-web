from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from .fetch_trace import (
    _answer_text,
    _clip,
    _requested_tool_calls,
    _tool_results,
    render_trace,
)


def _generation(**overrides) -> SimpleNamespace:
    """A Langfuse observation shaped like the ones ``agent.llm`` writes.

    SimpleNamespace rather than the real pydantic model: the renderer only ever
    reads attributes, and pinning the test to the SDK's model would make a
    Langfuse minor bump look like a bug in our code.
    """
    fields = {
        "type": "GENERATION",
        "name": "acompletion",
        "model": "gemini/gemini-3.6-flash",
        "latency": 1.5,
        "level": "DEFAULT",
        "status_message": None,
        "start_time": datetime(2026, 8, 7, 12, 0, 0),
        "input": [],
        "output": {},
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _trace(observations: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        id="trace-1",
        session_id="sess-1",
        user_id=None,
        timestamp=datetime(2026, 8, 7, 12, 0, 0),
        latency=2.0,
        total_cost=None,
        html_path="http://localhost:3000/trace/trace-1",
        observations=observations,
        scores=[],
    )


class TestToolResults:
    def test_picks_tool_replies_out_of_the_message_array(self):
        messages = [
            {"role": "system", "content": "you are an agent"},
            {"role": "user", "content": "gimana cara run acelents?"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "chunk about pnpm dev"},
        ]
        assert [r["tool_call_id"] for r in _tool_results(messages)] == ["c1"]

    def test_tolerates_a_non_list_input(self):
        """Older traces recorded input as a plain string; they must not crash."""
        assert _tool_results("some prompt") == []
        assert _tool_results(None) == []


class TestRequestedToolCalls:
    def test_reads_tool_calls_off_a_litellm_response(self):
        output = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "search_documentation",
                                    "arguments": '{"query":"run acelents"}',
                                }
                            }
                        ],
                    }
                }
            ]
        }
        assert _requested_tool_calls(output)[0]["function"]["name"] == "search_documentation"

    def test_returns_empty_for_a_plain_answer(self):
        assert _requested_tool_calls({"choices": [{"message": {"content": "hi"}}]}) == []

    def test_tolerates_malformed_output(self):
        assert _requested_tool_calls({}) == []
        assert _requested_tool_calls({"choices": []}) == []
        assert _requested_tool_calls("not a dict") == []


class TestAnswerText:
    def test_unwraps_the_assistant_message(self):
        output = {"choices": [{"message": {"content": "Jalankan `pnpm dev`."}}]}
        assert _answer_text(output) == "Jalankan `pnpm dev`."

    def test_falls_back_to_json_when_the_shape_is_unknown(self):
        assert "unexpected" in _answer_text({"unexpected": True})


class TestClip:
    def test_leaves_short_text_alone(self):
        assert _clip("short", 100) == "short"

    def test_reports_how_much_was_dropped(self):
        clipped = _clip("x" * 500, 100)
        assert clipped.startswith("x" * 100)
        assert "400 more chars" in clipped

    def test_none_disables_truncation(self):
        assert _clip("x" * 500, None) == "x" * 500


class TestRenderTrace:
    def test_retrieved_chunks_are_printed_before_the_answer(self, capsys):
        """The whole point of this renderer — see the module docstring."""
        retrieval_hop = _generation(
            input=[{"role": "tool", "tool_call_id": "c1", "content": "pnpm dev starts it"}],
            output={"choices": [{"message": {"content": "Jalankan `pnpm dev`."}}]},
        )
        render_trace(_trace([retrieval_hop]), max_chars=None)

        out = capsys.readouterr().out
        assert out.index("RETRIEVED") < out.index("ANSWER")
        assert "pnpm dev starts it" in out
        assert "Jalankan `pnpm dev`." in out

    def test_a_tool_calling_hop_shows_the_call_not_an_empty_answer(self, capsys):
        calling_hop = _generation(
            output={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "search_documentation",
                                        "arguments": '{"product_id":"acelents"}',
                                    }
                                }
                            ],
                        }
                    }
                ]
            }
        )
        render_trace(_trace([calling_hop]), max_chars=None)

        out = capsys.readouterr().out
        assert "CALLS" in out
        assert "search_documentation" in out
        assert "acelents" in out
        assert "ANSWER" not in out

    def test_observations_render_in_start_time_order(self, capsys):
        second = _generation(
            start_time=datetime(2026, 8, 7, 12, 0, 5),
            output={"choices": [{"message": {"content": "SECOND"}}]},
        )
        first = _generation(
            start_time=datetime(2026, 8, 7, 12, 0, 1),
            output={"choices": [{"message": {"content": "FIRST"}}]},
        )
        render_trace(_trace([second, first]), max_chars=None)

        out = capsys.readouterr().out
        assert out.index("FIRST") < out.index("SECOND")

    def test_a_run_that_never_reached_the_llm_says_so(self, capsys):
        render_trace(_trace([]), max_chars=None)
        assert "no observations" in capsys.readouterr().out
