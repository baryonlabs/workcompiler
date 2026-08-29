"""OpenWorkCompiler Core Optimizer Engine.

Provides Executor routing, promotion gate evaluations (Frontier LLM -> SLM / Code),
and training candidate generation for external fine-tuning backends.
"""

from core.optimizer.optimizer import (
    ExecutorOptimizer,
    TrainingCandidate,
    generate_training_candidate,
)

__all__ = [
    "ExecutorOptimizer",
    "TrainingCandidate",
    "generate_training_candidate",
]
