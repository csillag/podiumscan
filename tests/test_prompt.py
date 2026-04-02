import pytest
from booklet_reader.prompt import build_prompt, build_retry_prompt


class TestBuildPrompt:
    def test_includes_performer_names(self):
        performers = [
            {
                "name": "Nagy Eszter",
                "instruments": [
                    {"names": "hegedű / violin", "teachers": [], "accompanists": []}
                ],
            }
        ]
        prompt = build_prompt(performers)
        assert "Nagy Eszter" in prompt

    def test_includes_all_aliases(self):
        performers = [
            {
                "name": "Test Player",
                "instruments": [
                    {"names": "gordonka / cello", "teachers": [], "accompanists": []}
                ],
            }
        ]
        prompt = build_prompt(performers)
        assert "gordonka" in prompt
        assert "cello" in prompt

    def test_includes_json_schema(self):
        performers = [
            {
                "name": "Test",
                "instruments": [
                    {"names": "zongora / piano", "teachers": [], "accompanists": []}
                ],
            }
        ]
        prompt = build_prompt(performers)
        assert "event_name" in prompt
        assert "performance_date" in prompt
        assert "co_performers" in prompt
        assert "pieces" in prompt

    def test_multiple_performers(self):
        performers = [
            {
                "name": "Player One",
                "instruments": [{"names": "hegedű", "teachers": [], "accompanists": []}],
            },
            {
                "name": "Player Two",
                "instruments": [{"names": "fuvola / flute", "teachers": [], "accompanists": []}],
            },
        ]
        prompt = build_prompt(performers)
        assert "Player One" in prompt
        assert "Player Two" in prompt

    def test_returns_string(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers)
        assert isinstance(prompt, str)
        assert len(prompt) > 100


class TestBuildRetryPrompt:
    def test_includes_previous_response(self):
        prompt = build_retry_prompt("bad json here")
        assert "bad json here" in prompt

    def test_asks_for_valid_json(self):
        prompt = build_retry_prompt("{invalid")
        assert "valid JSON" in prompt

    def test_asks_for_all_fields(self):
        prompt = build_retry_prompt("[]")
        assert "required" in prompt.lower() or "field" in prompt.lower()


class TestBuildPromptComment:
    def test_no_comment_by_default(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers)
        assert "ADDITIONAL GUIDANCE" not in prompt

    def test_comment_included(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers, comment="Look at page 3")
        assert "ADDITIONAL GUIDANCE" in prompt
        assert "Look at page 3" in prompt

    def test_fallback_instruction_present(self):
        performers = [
            {
                "name": "Test",
                "instruments": [{"names": "zongora", "teachers": [], "accompanists": []}],
            }
        ]
        prompt = build_prompt(performers)
        assert "plain text explanation" in prompt.lower() or "plain text" in prompt.lower()
