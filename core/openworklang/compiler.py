"""OpenWorkLang Compiler Engine.

Compiles OpenWorkLang (.work) AST sources into:
1. OpenWorkCompiler WorkIR (work.yaml) AST model for durable execution.
2. LinkML Schema definitions (YAML).
3. BEHAVIOR.md process contract specifications.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.openworklang.ast import OpenWorkLangAST
from core.openworklang.parser import parse_openworklang
from core.work_ir import WorkIR, ExecutorDef, ExecutorType, save_work_ir


class OpenWorkLangCompiler:
    """Compiles higher-level OpenWorkLang agent DSL sources into runtime WorkIR and LinkML models."""

    def compile_ast_to_work_ir(self, ast: OpenWorkLangAST) -> WorkIR:
        """Compile an OpenWorkLangAST instance into a executable WorkIR AST."""
        actions = ast.workflow or list(ast.executors.keys())
        if not actions and ast.tools:
            actions = [t.split("(")[0].strip() for t in ast.tools]

        states = ["initialized"] + [f"{act}_completed" for act in actions]

        # Convert executor mapping
        executors_def: Dict[str, ExecutorDef] = {}
        for act in actions:
            exec_type_str = ast.executors.get(act, "code").lower()
            if exec_type_str == "llm":
                exec_type_str = "frontier_llm"
            try:
                exec_type = ExecutorType(exec_type_str)
            except ValueError:
                exec_type = ExecutorType.CODE

            handler = f"services.{act}" if exec_type == ExecutorType.CODE else (
                f"rules.{act}" if exec_type == ExecutorType.RULE else None
            )

            executors_def[act] = ExecutorDef(
                type=exec_type,
                handler=handler,
                preferred=f"models/{ast.name}-{act}-slm" if exec_type == ExecutorType.SLM else None,
                fallback=["frontier_llm", "human"] if exec_type in (ExecutorType.SLM, ExecutorType.FRONTIER_LLM) else None,
            )

        # Build WorkIR instance
        inputs = list(ast.params) + [i for i in ast.inputs if i not in ast.params]
        kwargs: Dict[str, Any] = {}
        if ast.escalation:
            kwargs["escalation"] = dict(ast.escalation)
        work_ir = WorkIR(
            work=ast.name,
            version=ast.version,
            description=ast.goal or f"Compiled OpenWorkLang agent work definition for '{ast.name}'",
            inputs=inputs or ["request_data"],
            outputs=ast.outputs or ["result"],
            states=states,
            actions=actions,
            dependencies=ast.dependencies,
            invariants=ast.invariants,
            executors=executors_def,
            **kwargs,
        )

        return work_ir

    def compile_to_linkml_yaml(self, ast: OpenWorkLangAST) -> str:
        """Compile OpenWorkLangAST into LinkML authoring schema (YAML)."""
        class_prefix = "".join(part.title() for part in ast.name.replace("-", "_").split("_"))
        linkml_lines = [
            f"id: https://w3id.org/openworkcompiler/schemas/{ast.name}",
            f"name: {ast.name}",
            f"description: {ast.goal or 'OpenWorkLang compiled schema'}",
            "imports:",
            "  - linkml:types",
            "classes:",
            f"  {class_prefix}Input:",
            "    slots:",
        ]
        for inp in ast.inputs:
            linkml_lines.append(f"      - {inp}")

        linkml_lines.extend([
            f"  {class_prefix}Output:",
            "    slots:",
        ])
        for out in ast.outputs:
            linkml_lines.append(f"      - {out}")

        linkml_lines.extend(["slots:"])
        for field in set(ast.inputs + ast.outputs):
            linkml_lines.extend([
                f"  {field}:",
                "    range: string",
                "    required: false",
            ])

        return "\n".join(linkml_lines)

    def compile_file(
        self, source_path: Union[str, Path], output_work_yaml: Optional[Union[str, Path]] = None
    ) -> WorkIR:
        """Compile an OpenWorkLang file into WorkIR and optionally save work.yaml."""
        ast = parse_openworklang(source_path)
        work_ir = self.compile_ast_to_work_ir(ast)

        if output_work_yaml:
            save_work_ir(work_ir, output_work_yaml)

        return work_ir
