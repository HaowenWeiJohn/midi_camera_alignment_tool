"""Subprocess test: importing core and services must NOT import PyQt5.

This enforces the one-way dependency rule from the refactor spec.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap


def test_core_and_services_do_not_import_pyqt5():
    code = textwrap.dedent("""
        import importlib, sys
        # Poison: if anything tries to `import PyQt5`, it fails loudly.
        class _Poison:
            def __getattr__(self, name):
                raise AssertionError(f"PyQt5.{name} accessed from Qt-free code")
        sys.modules["PyQt5"] = _Poison()

        importlib.import_module("alignment_tool.core")
        importlib.import_module("alignment_tool.core.errors")
        importlib.import_module("alignment_tool.core.models")
        importlib.import_module("alignment_tool.core.engine")
        importlib.import_module("alignment_tool.core.persistence")
        importlib.import_module("alignment_tool.services")
        importlib.import_module("alignment_tool.services.alignment_service")
        importlib.import_module("alignment_tool.services.level2_controller")

        assert "PyQt5.QtCore" not in sys.modules, "PyQt5.QtCore leaked"
        assert "PyQt5.QtWidgets" not in sys.modules, "PyQt5.QtWidgets leaked"
    """)
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Qt-free import check failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
