"""podiumscan — Extract performance data from music program booklets."""

import argparse
import json
import os
import sys


def _find_example_config():
    """Find config.example.yaml relative to the package installation."""
    package_dir = os.path.dirname(os.path.abspath(__file__))
    # In development: config.example.yaml is one level up from the package
    candidate = os.path.join(package_dir, "..", "config.example.yaml")
    if os.path.exists(candidate):
        return os.path.abspath(candidate)
    # Installed: should be included as package data
    candidate = os.path.join(package_dir, "config.example.yaml")
    if os.path.exists(candidate):
        return candidate
    return None


def main():
    # 1. Check Python dependencies
    try:
        from podiumscan.dependencies import check_python_deps, DependencyError
        check_python_deps()
    except ImportError:
        print(
            "Error: podiumscan package not found.",
            file=sys.stderr,
        )
        sys.exit(2)
    except DependencyError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    from podiumscan.config import load_config, validate_config, ensure_config, get_api_key, ConfigError
    from podiumscan.converter import (
        detect_file_type, convert_to_pdf, render_pdf_to_images, read_image_file,
        ConversionError, FILE_TYPE_DOCUMENT, FILE_TYPE_PDF, FILE_TYPE_IMAGE,
    )
    from podiumscan.dependencies import check_libreoffice
    from podiumscan.prompt import build_prompt
    from podiumscan.llm import run_cascade, get_mime_type, LLMError
    from podiumscan.gaps import fill_gaps

    # 2. Parse args
    parser = argparse.ArgumentParser(
        prog="podiumscan",
        description="Extract performance data from music program booklets.",
    )
    parser.add_argument("document", help="Path to the document file (PDF, DOC, DOCX, ODT, or image)")
    parser.add_argument("-c", "--comment", help="Additional guidance for the LLM (e.g. 'Look at page 3')")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show LLM explanation text on stderr")
    args = parser.parse_args()

    document_path = os.path.abspath(args.document)

    # 3. Config check
    config_path = os.path.expanduser("~/.config/podiumscan/config.yaml")
    example_path = _find_example_config()

    if example_path is None:
        print("Error: config.example.yaml not found.", file=sys.stderr)
        sys.exit(2)

    try:
        exists = ensure_config(config_path, example_path)
        if not exists:
            print(
                f"Before reading, please fill in your configuration at {config_path}",
                file=sys.stderr,
            )
            sys.exit(2)
        config = load_config(config_path)
        validate_config(config)
        with open(config_path, "rb") as f:
            config_bytes = f.read()
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 4. Detect file type
    try:
        file_type = detect_file_type(document_path)
    except ConversionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 5. System dependency check for documents needing libreoffice
    if file_type == FILE_TYPE_DOCUMENT:
        try:
            check_libreoffice()
        except DependencyError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)

    # 6. Prepare cascade inputs
    document_bytes = None
    document_mime = None
    pdf_bytes = None
    image_list = None

    try:
        if file_type == FILE_TYPE_DOCUMENT:
            with open(document_path, "rb") as f:
                document_bytes = f.read()
            document_mime = get_mime_type(document_path)
            pdf_path = convert_to_pdf(document_path)
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            image_list = render_pdf_to_images(pdf_path)

        elif file_type == FILE_TYPE_PDF:
            with open(document_path, "rb") as f:
                pdf_bytes = f.read()
            image_list = render_pdf_to_images(document_path)

        elif file_type == FILE_TYPE_IMAGE:
            img_bytes = read_image_file(document_path)
            image_list = [img_bytes]

    except ConversionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 7. Build prompt and run cascade
    prompt = build_prompt(config["performers"], comment=args.comment)
    api_key = get_api_key(config, "model")

    try:
        results = run_cascade(
            model=config["model"],
            api_key=api_key,
            prompt=prompt,
            document_bytes=document_bytes,
            document_mime=document_mime,
            pdf_bytes=pdf_bytes,
            image_list=image_list,
            verbose=args.verbose,
            config_bytes=config_bytes,
        )
    except LLMError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    # 8. Fill gaps
    if results:
        results = fill_gaps(results, config["performers"])

    # 9. Output
    if results:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
