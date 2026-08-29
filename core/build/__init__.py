"""OpenWorkCompiler build backend.

Lowers a compiled Work IR into an executable artifact tree (``build/<work>/``):
Python handlers for the code tier, declarative rule files, ML/SLM training
packages, frontier-LLM prompt contracts and human review checklists — plus a
loader that wires those artifacts back into the DurableRuntimeEngine.
"""

from core.build.emitter import BuildArtifact, BuildManifest, emit_build
from core.build.loader import load_build_into_engine

__all__ = ["BuildArtifact", "BuildManifest", "emit_build", "load_build_into_engine"]
