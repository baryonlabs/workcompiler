"""OpenWorkLang integration for OpenWorkCompiler.

The language itself lives in the ``openworklang`` package, vendored as a git submodule at
``vendor/openworklang`` (https://github.com/baryonlabs/openworklang). This module makes it
importable without installation and adapts its plain Work IR dictionaries to the runtime's
``WorkIR`` model. Clone with ``git clone --recurse-submodules`` or run
``git submodule update --init`` if ``vendor/openworklang`` is empty.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Union

_VENDOR = Path(__file__).resolve().parents[2] / "vendor" / "openworklang"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

try:
    from openworklang import OpenWorkLangAST, compile_ast_to_work_dict, compile_to_linkml_yaml, parse_openworklang
except ImportError as exc:  # pragma: no cover - environment problem, not a code path
    raise ImportError(
        "openworklang is not available. Initialise the submodule: git submodule update --init vendor/openworklang"
    ) from exc

from core.work_ir import WorkIR, save_work_ir


class OpenWorkLangCompiler:
    """Compile OpenWorkLang ASTs into the runtime's WorkIR model (and LinkML)."""

    def compile_ast_to_work_ir(self, ast: OpenWorkLangAST) -> WorkIR:
        return WorkIR.model_validate(compile_ast_to_work_dict(ast))

    def compile_to_linkml_yaml(self, ast: OpenWorkLangAST) -> str:
        return compile_to_linkml_yaml(ast)

    def compile_file(self, source_path: Union[str, Path], output_work_yaml: Optional[Union[str, Path]] = None) -> WorkIR:
        work_ir = self.compile_ast_to_work_ir(parse_openworklang(source_path))
        if output_work_yaml:
            save_work_ir(work_ir, output_work_yaml)
        return work_ir


__all__ = ["OpenWorkLangAST", "parse_openworklang", "OpenWorkLangCompiler", "compile_ast_to_work_dict", "compile_to_linkml_yaml"]
