import pytest
from unittest.mock import patch
from podiumscan.dependencies import check_python_deps, check_libreoffice, DependencyError


class TestCheckPythonDeps:
    def test_all_present(self):
        check_python_deps()

    def test_missing_package(self):
        with patch("importlib.import_module", side_effect=ImportError("no module")):
            with pytest.raises(DependencyError, match="pip install"):
                check_python_deps()


class TestCheckLibreoffice:
    def test_found(self):
        with patch("shutil.which", return_value="/usr/bin/libreoffice"):
            check_libreoffice()

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(DependencyError, match="libreoffice"):
                check_libreoffice()
