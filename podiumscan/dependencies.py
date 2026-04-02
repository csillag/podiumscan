import importlib
import shutil


class DependencyError(Exception):
    pass


REQUIRED_PACKAGES = {
    "litellm": "litellm",
    "yaml": "PyYAML",
    "fitz": "PyMuPDF",
}


def check_python_deps():
    """Check that all required Python packages are importable."""
    missing = []
    for module_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)
    if missing:
        packages = " ".join(missing)
        raise DependencyError(
            f"Error: Required packages not installed. Install with: pip install {packages}"
        )


def check_libreoffice():
    """Check that libreoffice is available on PATH."""
    if shutil.which("libreoffice") is None:
        raise DependencyError(
            "Error: 'libreoffice' is required for DOC/DOCX/ODT conversion but was not found. "
            "Install it with: sudo apt install libreoffice"
        )
