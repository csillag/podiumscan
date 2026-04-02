import json
import base64
import pytest
from unittest.mock import patch, MagicMock
from podiumscan.llm import (
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
        doc_parts = [c for c in content if c["type"] == "file"]
        assert len(text_parts) == 1
        assert len(doc_parts) == 1
        assert text_parts[0]["text"] == "Find performers"
        assert doc_parts[0]["file"]["format"] == "application/pdf"
        assert "base64," in doc_parts[0]["file"]["file_data"]


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
        results, explanation = parse_llm_response(raw)
        assert isinstance(results, list)
        assert results[0]["event_name"] == "Test"
        assert explanation is None

    def test_empty_array(self):
        results, explanation = parse_llm_response("[]")
        assert results == []
        assert explanation is None

    def test_strips_markdown_fences(self):
        raw = '```json\n[{"event_name": "Test"}]\n```'
        results, explanation = parse_llm_response(raw)
        assert results[0]["event_name"] == "Test"
        assert explanation is None

    def test_json_embedded_in_explanation(self):
        raw = 'I found the performer.\n\n[{"event_name": "Test"}]\n\nHope this helps.'
        results, explanation = parse_llm_response(raw)
        assert results[0]["event_name"] == "Test"
        assert "I found the performer" in explanation

    def test_json_with_markdown_fences_in_explanation(self):
        raw = 'Here is the result:\n\n```json\n[{"event_name": "Test"}]\n```\n\nDone.'
        results, explanation = parse_llm_response(raw)
        assert results[0]["event_name"] == "Test"

    def test_plain_text_only(self):
        results, explanation = parse_llm_response("I could not find any performers.")
        assert results is None
        assert "could not find" in explanation

    def test_not_an_array(self):
        results, explanation = parse_llm_response('{"event_name": "Test"}')
        assert results is None
        assert explanation is not None


class TestTryLevel:
    def test_success_first_attempt(self):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good):
            result, raw = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result[0]["event_name"] == "OK"
        assert raw == '[{"event_name": "OK"}]'

    def test_success_with_embedded_json(self):
        mixed = _mock_response('Found it!\n[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=mixed):
            result, raw = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result[0]["event_name"] == "OK"
        assert "Found it!" in raw

    def test_explanation_hidden_without_verbose(self, capsys):
        mixed = _mock_response('Found it!\n[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=mixed):
            try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt", verbose=False)
        captured = capsys.readouterr()
        assert "Found it" not in captured.err

    def test_explanation_shown_with_verbose(self, capsys):
        mixed = _mock_response('Found it!\n[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=mixed):
            try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt", verbose=True)
        captured = capsys.readouterr()
        assert "Found it" in captured.err
        assert "\033[36m" in captured.err

    def test_retry_on_plain_text(self):
        bad = _mock_response("I cannot parse this document.")
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", side_effect=[bad, good]):
            result, raw = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result[0]["event_name"] == "OK"

    def test_returns_none_after_two_failures(self):
        bad = _mock_response("not json")
        with patch("litellm.completion", return_value=bad):
            result, raw = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result is None
        assert raw is None

    def test_returns_none_on_api_error(self):
        with patch("litellm.completion", side_effect=Exception("API down")):
            result, raw = try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt")
        assert result is None
        assert raw is None

    def test_failure_always_prints_cyan(self, capsys):
        explanation = "I could not find any of the listed performers."
        bad = _mock_response(explanation)
        with patch("litellm.completion", return_value=bad):
            try_level("model", "key", [{"role": "user", "content": "hi"}], "prompt", verbose=False)
        captured = capsys.readouterr()
        assert explanation in captured.err
        assert "\033[36m" in captured.err


class TestRunCascade:
    def test_succeeds_at_level_1(self):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good), \
             patch("podiumscan.llm.read_cache", return_value=None), \
             patch("podiumscan.llm.write_cache"):
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
        with patch("litellm.completion", side_effect=[bad, bad, bad, bad, good]), \
             patch("podiumscan.llm.read_cache", return_value=None), \
             patch("podiumscan.llm.write_cache"):
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
        with patch("litellm.completion", return_value=bad), \
             patch("podiumscan.llm.read_cache", return_value=None), \
             patch("podiumscan.llm.write_cache"):
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


class TestRunCascadeNarration:
    def test_narrates_levels_on_stderr(self, capsys):
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", return_value=good), \
             patch("podiumscan.llm.read_cache", return_value=None), \
             patch("podiumscan.llm.write_cache"):
            run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=None,
                document_mime=None,
                pdf_bytes=b"fake pdf",
                image_list=None,
            )
        captured = capsys.readouterr()
        assert "Attempting PDF submission" in captured.err

    def test_narrates_fallback_on_stderr(self, capsys):
        bad = _mock_response("I cannot read this document.")
        good = _mock_response('[{"event_name": "OK"}]')
        with patch("litellm.completion", side_effect=[bad, bad, good]), \
             patch("podiumscan.llm.read_cache", return_value=None), \
             patch("podiumscan.llm.write_cache"):
            run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=None,
                document_mime=None,
                pdf_bytes=b"fake pdf",
                image_list=[b"\x89PNGfake"],
            )
        captured = capsys.readouterr()
        assert "Moving to next format" in captured.err


class TestRunCascadeCache:
    def test_cache_hit_skips_llm(self, capsys):
        cached_response = '[{"event_name": "Cached"}]'
        with patch("podiumscan.llm.read_cache", return_value=cached_response), \
             patch("podiumscan.llm.write_cache"), \
             patch("litellm.completion") as mock_llm:
            result = run_cascade(
                model="model",
                api_key="key",
                prompt="find performers",
                document_bytes=None,
                document_mime=None,
                pdf_bytes=b"fake pdf",
                image_list=None,
            )
        assert result[0]["event_name"] == "Cached"
        mock_llm.assert_not_called()
        captured = capsys.readouterr()
        assert "Cache hit" in captured.err
