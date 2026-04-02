import json
import re
import sys

import litellm

BEGIN_MARKER = "# --- BEGIN AVAILABLE MODELS ---"
END_MARKER = "# --- END AVAILABLE MODELS ---"

def extract_model_block(config_text):
    in_block = False
    models = []
    for line in config_text.splitlines():
        if BEGIN_MARKER in line:
            in_block = True
            continue
        if END_MARKER in line:
            break
        if in_block:
            match = re.match(r"^#\s+-\s+(.+)$", line)
            if match:
                models.append(match.group(1).strip())
    return models

def build_updated_model_block(models):
    lines = [BEGIN_MARKER, "# available_models:"]
    for model in sorted(models):
        lines.append(f"#   - {model}")
    lines.append(END_MARKER)
    return "\n".join(lines)

def update_config_file_models(config_path, new_models):
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    new_block = build_updated_model_block(new_models)
    pattern = re.compile(re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
    updated = pattern.sub(new_block, content)
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(updated)

def query_llm_for_models(model, api_key):
    prompt = """List all currently available LLM models from major providers that support PDF and/or image/vision input via their API.

For each model, give me the identifier in LiteLLM format: provider/model-name
For example: openai/gpt-4o, anthropic/claude-sonnet-4-20250514, gemini/gemini-2.5-pro

Only include models that:
1. Accept PDF or image input as part of their API
2. Are currently available (not deprecated or preview-only)
3. Have a known LiteLLM provider prefix

Return ONLY a JSON array of strings. No explanation, no markdown fences. Example:
["openai/gpt-4o", "anthropic/claude-sonnet-4-20250514"]"""

    try:
        response = litellm.completion(model=model, api_key=api_key, messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        print(f"Error: LLM API call failed: {e}", file=sys.stderr)
        sys.exit(1)

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        models = json.loads(raw)
    except json.JSONDecodeError:
        print("Error: LLM returned invalid JSON for model list.", file=sys.stderr)
        sys.exit(1)

    if not isinstance(models, list):
        print("Error: LLM returned non-list for model list.", file=sys.stderr)
        sys.exit(1)

    return [m for m in models if isinstance(m, str)]

def cross_reference_with_litellm(models):
    valid = []
    for model in models:
        try:
            litellm.get_model_info(model)
            valid.append(model)
        except Exception:
            pass
    return valid
