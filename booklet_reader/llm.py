import base64
import json
import os
import sys

import logging

import litellm

from booklet_reader.prompt import build_retry_prompt

# Suppress LiteLLM's verbose logging (provider lists, debug hints, etc.)
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class LLMError(Exception):
    pass


CYAN = "\033[36m"
RESET = "\033[0m"


def build_messages_with_document(prompt, doc_bytes, mime_type):
    """Build messages with a raw document file attached."""
    b64 = base64.b64encode(doc_bytes).decode("utf-8")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "file",
                    "file": {
                        "file_data": f"data:{mime_type};base64,{b64}",
                        "format": mime_type,
                    },
                },
            ],
        }
    ]


def build_messages_with_images(prompt, images):
    """Build messages with page images attached."""
    content = [{"type": "text", "text": prompt}]
    for img_bytes in images:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    return [{"role": "user", "content": content}]


def _strip_markdown_fences(text):
    """Strip markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_llm_response(raw_text):
    """Parse the LLM response, extracting JSON even if mixed with explanation text.

    Returns (results, explanation) tuple:
    - results: parsed list of dicts, or None if no valid JSON found
    - explanation: any non-JSON text from the response, or None
    """
    text = _strip_markdown_fences(raw_text.strip())

    # Try parsing the whole thing as JSON first
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result, None
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find a JSON array embedded in the text
    # Look for the outermost [...] block
    start = text.find("[")
    if start != -1:
        # Find the matching closing bracket
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    json_str = text[start:i + 1]
                    try:
                        result = json.loads(json_str)
                        if isinstance(result, list):
                            explanation = (text[:start] + text[i + 1:]).strip()
                            explanation = _strip_markdown_fences(explanation)
                            return result, explanation if explanation else None
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

    # Nothing parseable found
    return None, raw_text.strip()


def try_level(model, api_key, messages, prompt, verbose=False):
    """Try sending messages to the LLM. Retry once on invalid JSON with a nudge.

    Returns parsed results list on success, or None on failure.
    On success with explanation: prints explanation to stderr only if verbose.
    On failure: always prints the LLM's response to stderr in cyan.
    """
    for attempt in range(2):
        try:
            response = litellm.completion(model=model, api_key=api_key, messages=messages)
        except Exception as e:
            print(f"API error: {type(e).__name__}", file=sys.stderr)
            return None

        raw_text = response.choices[0].message.content
        results, explanation = parse_llm_response(raw_text)

        if results is not None:
            # Successful extraction
            if explanation and verbose:
                print(f"{CYAN}{explanation}{RESET}", file=sys.stderr)
            return results

        # No JSON found at all
        print(f"{CYAN}{explanation or raw_text}{RESET}", file=sys.stderr)
        if attempt == 0:
            print(
                "LLM returned invalid JSON. Retrying with guidance...",
                file=sys.stderr,
            )
            retry_prompt = build_retry_prompt(raw_text)
            messages = messages + [
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": retry_prompt},
            ]
            continue
        return None


_MIME_TYPES = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".pdf": "application/pdf",
}


def get_mime_type(filepath):
    """Get MIME type for a document file based on extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return _MIME_TYPES.get(ext)


_LEVEL_NAMES = {
    "raw document": "Attempting raw document submission...",
    "PDF": "Attempting PDF submission...",
    "images": "Attempting image submission...",
}


def run_cascade(model, api_key, prompt, document_bytes, document_mime, pdf_bytes, image_list, verbose=False):
    """Run the cascading LLM submission: raw document → PDF → images.

    Each level tries once, retries on invalid JSON with a nudge, then falls to next level.
    Raises LLMError if all levels fail.
    """
    print(f"Using model: {model}", file=sys.stderr)
    levels = []

    # Level 1: Raw document (DOC/DOCX/ODT only)
    if document_bytes is not None and document_mime is not None:
        messages = build_messages_with_document(prompt, document_bytes, document_mime)
        levels.append(("raw document", messages))

    # Level 2: PDF
    if pdf_bytes is not None:
        messages = build_messages_with_document(prompt, pdf_bytes, "application/pdf")
        levels.append(("PDF", messages))

    # Level 3: Images
    if image_list is not None:
        messages = build_messages_with_images(prompt, image_list)
        levels.append(("images", messages))

    for i, (level_name, messages) in enumerate(levels):
        print(_LEVEL_NAMES[level_name], file=sys.stderr)
        result = try_level(model, api_key, messages, prompt, verbose=verbose)
        if result is not None:
            return result
        if i < len(levels) - 1:
            print("Moving to next format...", file=sys.stderr)

    raise LLMError("Error: All input format levels failed. LLM could not produce valid output.")
