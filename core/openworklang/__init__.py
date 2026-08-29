"""OpenWorkLang: Agent Programming Language for OpenWorkCompiler.

Enables human and developer authoring of high-level agent work specifications
which compile into executable WorkIR (work.yaml) and LinkML domain schemas.
"""

from core.openworklang.ast import OpenWorkLangAST
from core.openworklang.parser import parse_openworklang
from core.openworklang.compiler import OpenWorkLangCompiler

__all__ = [
    "OpenWorkLangAST",
    "parse_openworklang",
    "OpenWorkLangCompiler",
]
