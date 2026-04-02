import os
import pytest
from unittest.mock import patch, MagicMock
from podiumscan.converter import (
    detect_file_type,
    convert_to_pdf,
    render_pdf_to_images,
    read_image_file,
    ConversionError,
    FILE_TYPE_DOCUMENT,
    FILE_TYPE_PDF,
    FILE_TYPE_IMAGE,
)


class TestDetectFileType:
    def test_pdf(self):
        assert detect_file_type("document.pdf") == FILE_TYPE_PDF

    def test_doc(self):
        assert detect_file_type("document.doc") == FILE_TYPE_DOCUMENT

    def test_docx(self):
        assert detect_file_type("document.docx") == FILE_TYPE_DOCUMENT

    def test_odt(self):
        assert detect_file_type("document.odt") == FILE_TYPE_DOCUMENT

    def test_png(self):
        assert detect_file_type("poster.png") == FILE_TYPE_IMAGE

    def test_jpg(self):
        assert detect_file_type("poster.jpg") == FILE_TYPE_IMAGE

    def test_jpeg(self):
        assert detect_file_type("poster.jpeg") == FILE_TYPE_IMAGE

    def test_webp(self):
        assert detect_file_type("poster.webp") == FILE_TYPE_IMAGE

    def test_uppercase(self):
        assert detect_file_type("DOCUMENT.PDF") == FILE_TYPE_PDF

    def test_unsupported(self):
        with pytest.raises(ConversionError, match="Unsupported file type"):
            detect_file_type("document.txt")


class TestConvertToPdf:
    def test_pdf_passthrough(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")
        result = convert_to_pdf(str(pdf_file))
        assert result == str(pdf_file)

    def test_doc_conversion(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch("glob.glob", return_value=["/tmp/out/test.pdf"]):
                result = convert_to_pdf(str(tmp_path / "test.doc"))
            mock_run.assert_called_once()
            assert "libreoffice" in mock_run.call_args[0][0][0]

    def test_nonexistent_file(self):
        with pytest.raises(ConversionError, match="not found"):
            convert_to_pdf("/nonexistent/file.doc")


class TestRenderPdfToImages:
    def test_renders_pages(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample-data")
        pdfs = [f for f in os.listdir(sample_dir) if f.endswith(".pdf")] if os.path.isdir(sample_dir) else []
        if not pdfs:
            pytest.skip("No sample PDFs available")
        pdf_path = os.path.join(sample_dir, pdfs[0])
        images = render_pdf_to_images(pdf_path)
        assert len(images) > 0
        for img in images:
            assert isinstance(img, bytes)
            assert img[:8] == b"\x89PNG\r\n\x1a\n"


class TestReadImageFile:
    def test_reads_png(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakedata")
        result = read_image_file(str(img_file))
        assert result == b"\x89PNG\r\n\x1a\nfakedata"

    def test_nonexistent(self):
        with pytest.raises(ConversionError, match="not found"):
            read_image_file("/nonexistent/poster.png")
