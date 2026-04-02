import glob
import os
import subprocess
import tempfile

import fitz  # PyMuPDF


class ConversionError(Exception):
    pass


FILE_TYPE_DOCUMENT = "document"  # DOC, DOCX, ODT
FILE_TYPE_PDF = "pdf"
FILE_TYPE_IMAGE = "image"

_DOCUMENT_EXTENSIONS = {".doc", ".docx", ".odt"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def detect_file_type(filepath):
    """Detect file type category by extension. Returns FILE_TYPE_* constant."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return FILE_TYPE_PDF
    elif ext in _DOCUMENT_EXTENSIONS:
        return FILE_TYPE_DOCUMENT
    elif ext in _IMAGE_EXTENSIONS:
        return FILE_TYPE_IMAGE
    else:
        raise ConversionError(
            f"Error: Unsupported file type '{ext}'. "
            f"Supported: .pdf, .doc, .docx, .odt, .png, .jpg, .jpeg, .webp"
        )


def convert_to_pdf(filepath):
    """Convert DOC/DOCX/ODT to PDF using libreoffice. Returns path to PDF.

    If already a PDF, returns the original path.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        if not os.path.exists(filepath):
            raise ConversionError(f"Error: File not found: '{filepath}'")
        return filepath

    tmp_dir = tempfile.mkdtemp(prefix="podiumscan-")
    try:
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp_dir,
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise ConversionError(
                f"Error: libreoffice conversion failed: {result.stderr}"
            )
        basename = os.path.splitext(os.path.basename(filepath))[0]
        pdf_files = glob.glob(os.path.join(tmp_dir, basename + ".pdf"))
        if not pdf_files:
            if not os.path.exists(filepath):
                raise ConversionError(f"Error: File not found: '{filepath}'")
            raise ConversionError(
                "Error: libreoffice conversion produced no output"
            )
        return pdf_files[0]
    except subprocess.TimeoutExpired:
        raise ConversionError("Error: libreoffice conversion timed out")


def render_pdf_to_images(pdf_path, dpi=200):
    """Render each page of a PDF to PNG bytes. Returns a list of PNG byte strings."""
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ConversionError(f"Error: Failed to open PDF '{pdf_path}': {e}")

    images = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def read_image_file(filepath):
    """Read an image file and return its raw bytes."""
    if not os.path.exists(filepath):
        raise ConversionError(f"Error: File not found: '{filepath}'")
    with open(filepath, "rb") as f:
        return f.read()
