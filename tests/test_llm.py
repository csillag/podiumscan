import json
import base64
import pytest
from unittest.mock import patch, MagicMock
from booklet_reader.llm import (
    build_messages_with_document,
    build_messages_with_images,
    parse_llm_response,
    try_level,
    run_cascade,
    LLMError,
)


def _mock_response(content):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


class TestBuildMessagesWithDocument:
    def test_includes_prompt_and_file(self):
        messages = build_messages_with_document("Find performers", b"%PDF-fake", "application/pdf")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        content = messages[0]["content"]
        text_parts = [c for c in content if c["type"] == "text"]
        doc_parts = [c for c in content if c["type"] == "image_url"]
        assert len(text_parts) == 1
        assert len(doc_parts) == 1
        assert text_parts[0]["text"] == "Find performers"


class TestBuildMessagesWithImages:
    def test_includes_prompt_and_images(self):
        images = [b"\x89PNG\r\n\x1a\nfake1", b"\x89PNG\r\n\x1a\nfake2"]
        messages = build_messages_with_images("Find performers", images)
        content = messages[0]["content"]
        text_parts = [c for c in content if c["type"] == "text"]
        image_parts = [c for c in content if c["type"] == "image_url"]
        assert len(text_parts) == 1
        assert len(image_parts) == 2

    def test_image_encoding(self):
        png_bytes = b"\x89PNG\r\n\x1a\nfakedata"
        messages = build_messages_with_images("prompt", [png_bytes])
        image_part = messages[0]["content"][1]
        expected_b64 = base64.b64encode(png_bytes).decode("utf-8")
        assert image_part["image_url"]["url"] == f"data:image/png;base64,{expected_b64}"


class TestParseLlmResponse:
    def test_valid_json_array(self):
        raw = json.dumps([{"event_name": "Test", "performer": "A"}])
        result = parse_llm_response(raw)
        assert isinstance(result, list)
        assert result[0]["event_name"] == "Test"

    def test_empty_array(self):
        result = parse_llm_response("[]")
        assert result == []

    def test_strips_markdown_fences(self):
        raw = '```json\n[{"event_name": "Test"}]\n```'
        result = parse_llm_response(raw)
        assert result[0]["event_name"] == "Test"

    def test_invalid_json(self):
        with pytest.raises(LLMError, match="invalid JSON"):
            parse_llm_response("not json at all")

    def test_not_an_array(self):
        with pytest.raises(LLMError, match="expected a JSON array"):
            parse_llm_response('{"event_name": "Test"}')


class TestTryLevel:
    def test_success_first_attempt(self):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result[0]["event_name"] == "OK"

    def test_retry_on_bad_json(self):
        bad = _mock_response("not json")
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", side_effect=[bad, good]):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result[0]["event_name"] == "OK"

    def test_returns_none_after_two_bad_json(self):
        bad = _mock_response("not json")
        with patch("litellm.completion", return_value=bad):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result is None

    def test_returns_none_on_api_error(self):
        with patch("litellm.completion", side_effect=Exception("API down")):
            result = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result is None


class TestRunCascade:
    def test_succeeds_at_level_1(self):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good):
            result = run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=b"fake doc",
                document_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                pdf_bytes=None,
                image_list=None,
            )
        assert result[0]["event_name"] == "OK"

    def test_falls_through_to_images(self):
        bad = _mock_response("not json")
        good = _mock_response('[{"event_name": "OK"}]')
        # Level 1 (doc): bad, bad. Level 2 (pdf): bad, bad. Level 3 (images): good.
        with patch("litellm.completion", side_effect=[bad, bad, bad, bad, good]):
            result = run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=b"fake doc",
                document_mime="application/msword",
                pdf_bytes=b"fake pdf",
                image_list=[b"\x89PNGfake"],
            )
        assert result[0]["event_name"] == "OK"

    def test_hard_fail_all_levels(self):
        bad = _mock_response("not json")
        with patch("litellm.completion", return_value=bad):
            with pytest.raises(LLMError, match="All input format levels failed"):
                run_cascade(
                    model="model",
                    api_key="key",
                    prompt="find performers",
                    document_bytes=None,
                    document_mime=None,
                    pdf_bytes=b"fake pdf",
                    image_list=[b"\x89PNGfake"],
                )
