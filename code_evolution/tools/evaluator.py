"""
Evaluation system for OpenEvolve
"""

import asyncio
import importlib.util
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

@dataclass
class EvaluatorConfig:
    """Configuration for program evaluation"""

    # General settings
    timeout: int = 300  # Maximum evaluation time in seconds
    max_retries: int = 3

    # Resource limits for evaluation
    # Note: resource limits not implemented
    memory_limit_mb: Optional[int] = None
    cpu_limit: Optional[float] = None



    # Parallel evaluation
    parallel_evaluations: int = 1
    # Note: distributed evaluation not implemented
    distributed: bool = False

    # Artifact handling
    enable_artifacts: bool = True
    max_artifact_storage: int = 100 * 1024 * 1024  # 100MB per program


@dataclass
class EvaluationResult:
    """
    Result of program evaluation containing both metrics and optional artifacts

    Examples:
        ✅ Correct: {"combined_score": 0.85, "prompt_length": 1247, "execution_time": 0.234}
    """

    metrics: Dict[str, float]  # mandatory - existing contract
    artifacts: Dict[str, Union[str, bytes]] = field(default_factory=dict)  # optional side-channel
    stdout: Optional[str] = None  # captured stdout from program execution
    stderr: Optional[str] = None  # captured stderr from program execution

    @classmethod
    def from_dict(cls, metrics: Dict[str, float]) -> "EvaluationResult":
        """Auto-wrap dict returns for backward compatibility"""
        return cls(metrics=metrics)

    def to_dict(self) -> Dict[str, float]:
        """Backward compatibility - return just metrics"""
        return self.metrics

    def has_artifacts(self) -> bool:
        """Check if this result contains any artifacts"""
        return bool(self.artifacts)

    def get_artifact_keys(self) -> list:
        """Get list of artifact keys"""
        return list(self.artifacts.keys())

    def get_artifact_size(self, key: str) -> int:
        """Get size of a specific artifact in bytes"""
        if key not in self.artifacts:
            return 0

        value = self.artifacts[key]
        if isinstance(value, str):
            return len(value.encode("utf-8"))
        elif isinstance(value, bytes):
            return len(value)
        else:
            return len(str(value).encode("utf-8"))

    def get_total_artifact_size(self) -> int:
        """Get total size of all artifacts in bytes"""
        return sum(self.get_artifact_size(key) for key in self.artifacts.keys())


def format_metrics_safe(metrics: Dict[str, Any]) -> str:
    """
    Safely format metrics dictionary for logging, handling both numeric and string values.

    Args:
        metrics: Dictionary of metric names to values

    Returns:
        Formatted string representation of metrics
    """
    if not metrics:
        return ""

    formatted_parts = []
    for name, value in metrics.items():
        # Check if value is numeric (int, float)
        if isinstance(value, (int, float)):
            try:
                # Only apply float formatting to numeric values
                formatted_parts.append(f"{name}={value:.4f}")
            except (ValueError, TypeError):
                # Fallback to string representation if formatting fails
                formatted_parts.append(f"{name}={value}")
        else:
            # For non-numeric values (strings, etc.), just convert to string
            formatted_parts.append(f"{name}={value}")

    return ", ".join(formatted_parts)



class Evaluator:
    """
    Evaluates programs and assigns scores

    The evaluator is responsible for executing programs, measuring their performance,
    and assigning scores based on the evaluation criteria.
    """

    def __init__(
        self,
        config: EvaluatorConfig,
        evaluation_file: str,
        suffix: Optional[str] = ".py",
    ):
        self.config = config
        self.evaluation_file = evaluation_file
        self.program_suffix = suffix

        # Set up evaluation function if file exists
        self._load_evaluation_function()

        # Pending artifacts storage for programs
        self._pending_artifacts: Dict[str, Dict[str, Union[str, bytes]]] = {}

        logger.info(f"Initialized evaluator with {evaluation_file}")

    def _load_evaluation_function(self) -> None:
        """Load the evaluation function from the evaluation file"""
        if not os.path.exists(self.evaluation_file):
            raise ValueError(f"Evaluation file {self.evaluation_file} not found")

        try:
            # Add the evaluation file's directory to Python path so it can import local modules
            eval_dir = os.path.dirname(os.path.abspath(self.evaluation_file))
            if eval_dir not in sys.path:
                sys.path.insert(0, eval_dir)
                logger.debug(f"Added {eval_dir} to Python path for local imports")

            spec = importlib.util.spec_from_file_location("evaluation_module", self.evaluation_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Failed to load spec from {self.evaluation_file}")

            module = importlib.util.module_from_spec(spec)
            sys.modules["evaluation_module"] = module
            spec.loader.exec_module(module)

            if not hasattr(module, "evaluate"):
                raise AttributeError(
                    f"Evaluation file {self.evaluation_file} does not contain an 'evaluate' function"
                )

            self.evaluate_function = module.evaluate
            logger.info(f"Successfully loaded evaluation function from {self.evaluation_file}")
        except Exception as e:
            logger.error(f"Error loading evaluation function: {str(e)}")
            raise

    async def evaluate_program(
        self,
        program_code: str,
        program_id: str = "",
    ) -> EvaluationResult:
        """
        Evaluate a program and return evaluation result

        Args:
            program_code: Code to evaluate
            program_id: Optional ID for logging

        Returns:
            EvaluationResult with metrics, stdout, stderr, and artifacts
        """
        start_time = time.time()
        program_id_str = f" {program_id}" if program_id else ""

        # Check if artifacts are enabled
        artifacts_enabled = os.environ.get("ENABLE_ARTIFACTS", "true").lower() == "true"

        # Retry logic for evaluation
        last_exception = None
        for attempt in range(self.config.max_retries + 1):
            # Create a temporary file for the program
            with tempfile.NamedTemporaryFile(suffix=self.program_suffix, delete=False) as temp_file:
                temp_file.write(program_code.encode("utf-8"))
                temp_file_path = temp_file.name

            try:
                # Run evaluation
                result = await self._direct_evaluate(temp_file_path)

                # Process the result based on type
                eval_result = self._process_evaluation_result(result)

                # Check if this was a timeout and capture artifacts if enabled
                if artifacts_enabled and program_id and eval_result.metrics.get("timeout") is True:
                    if program_id not in self._pending_artifacts:
                        self._pending_artifacts[program_id] = {}

                    self._pending_artifacts[program_id].update(
                        {
                            "timeout": True,
                            "timeout_duration": self.config.timeout,
                            "failure_stage": "evaluation",
                            "error_type": "timeout",
                        }
                    )

                # Store artifacts if enabled and present
                if artifacts_enabled and eval_result.has_artifacts() and program_id:
                    if program_id not in self._pending_artifacts:
                        self._pending_artifacts[program_id] = {}

                    # Merge eval_result artifacts
                    self._pending_artifacts[program_id].update(eval_result.artifacts)
                    logger.debug(
                        f"Program{program_id_str} returned artifacts: "
                        f"{eval_result.artifacts}"
                    )

                elapsed = time.time() - start_time
                logger.info(
                    f"Evaluated program{program_id_str} in {elapsed:.2f}s: "
                    f"{format_metrics_safe(eval_result.metrics)}"
                )

                # Return full evaluation result
                return eval_result

            except asyncio.TimeoutError:
                # Handle timeout specially - don't retry, just return timeout result
                logger.warning(f"Evaluation timed out after {self.config.timeout}s")

                # Capture timeout artifacts if enabled
                if artifacts_enabled and program_id:
                    self._pending_artifacts[program_id] = {
                        "timeout": True,
                        "timeout_duration": self.config.timeout,
                        "failure_stage": "evaluation",
                        "error_type": "timeout",
                    }

                return EvaluationResult(metrics={"error": 0.0, "timeout": True})

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Evaluation attempt {attempt + 1}/{self.config.max_retries + 1} failed for program{program_id_str}: {str(e)}"
                )
                traceback.print_exc()

                # Capture failure artifacts if enabled
                if artifacts_enabled and program_id:
                    self._pending_artifacts[program_id] = {
                        "stderr": str(e),
                        "traceback": traceback.format_exc(),
                        "failure_stage": "evaluation",
                        "attempt": attempt + 1,
                    }

                # If this is not the last attempt, wait a bit before retrying
                if attempt < self.config.max_retries:
                    await asyncio.sleep(1.0)  # Wait 1 second before retry

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        # All retries failed
        logger.error(
            f"All evaluation attempts failed for program{program_id_str}. Last error: {str(last_exception)}"
        )
        return EvaluationResult(metrics={"error": 0.0})

    def _process_evaluation_result(self, result: Any) -> EvaluationResult:
        """
        Process evaluation result to handle both dict and EvaluationResult returns

        Args:
            result: Raw result from evaluation function

        Returns:
            EvaluationResult instance
        """
        if isinstance(result, dict):
            # Backward compatibility - wrap dict in EvaluationResult
            return EvaluationResult.from_dict(result)
        elif isinstance(result, EvaluationResult):
            # New format - use directly
            return result
        else:
            # Error case - return error metrics
            logger.warning(f"Unexpected evaluation result type: {type(result)}")
            return EvaluationResult(metrics={"error": 0.0})

    def get_pending_artifacts(self, program_id: str) -> Optional[Dict[str, Union[str, bytes]]]:
        """
        Get and clear pending artifacts for a program

        Args:
            program_id: Program ID

        Returns:
            Artifacts dictionary or None if not found
        """
        return self._pending_artifacts.pop(program_id, None)

    async def _direct_evaluate(
        self, program_path: str
    ) -> Union[Dict[str, float], EvaluationResult]:
        """
        Directly evaluate a program using the evaluation function with timeout

        Args:
            program_path: Path to the program file

        Returns:
            Dictionary of metrics or EvaluationResult with metrics and artifacts

        Raises:
            asyncio.TimeoutError: If evaluation exceeds timeout
            Exception: If evaluation function raises an exception
        """

        # Create a coroutine that runs the evaluation function in an executor
        # with stdout/stderr capture
        async def run_evaluation():
            loop = asyncio.get_event_loop()
            
            # Capture stdout and stderr
            import io
            import contextlib
            
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                result = await loop.run_in_executor(None, self.evaluate_function, program_path)
            
            # Get captured output
            stdout_text = stdout_capture.getvalue()
            stderr_text = stderr_capture.getvalue()
            
            # If result is a dict, convert to EvaluationResult and add stdout/stderr
            if isinstance(result, dict):
                if 'metrics' in result:
                    # New format with metrics/artifacts
                    eval_result = EvaluationResult(
                        metrics=result['metrics'],
                        artifacts=result.get('artifacts', {}),
                        stdout=stdout_text if stdout_text else None,
                        stderr=stderr_text if stderr_text else None
                    )
                else:
                    # Old format - just metrics
                    eval_result = EvaluationResult(
                        metrics=result,
                        stdout=stdout_text if stdout_text else None,
                        stderr=stderr_text if stderr_text else None
                    )
                return eval_result
            elif isinstance(result, EvaluationResult):
                # Add stdout/stderr to existing result
                result.stdout = stdout_text if stdout_text else result.stdout
                result.stderr = stderr_text if stderr_text else result.stderr
                return result
            else:
                return result

        # Run the evaluation with timeout - let exceptions bubble up for retry handling
        result = await asyncio.wait_for(run_evaluation(), timeout=self.config.timeout)

        # Return result as-is to be processed by _process_evaluation_result
        return result
