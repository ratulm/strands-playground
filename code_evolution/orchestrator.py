"""Evolution Orchestrator for the program evolution system.

This module implements the main orchestration logic that coordinates the
evolution process across multiple iterations. It manages the Swarm, tracks
results, and extracts insights from agent interactions.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

from .agents import create_researcher_agent, create_supervisor_agent
from .core.streaming_logger import StreamingConversationLogger
from strands.multiagent import Swarm

logger = logging.getLogger(__name__)


class EvolutionOrchestrator:
    """Orchestrates a single program evolution using a Swarm.

    The orchestrator manages the evolution workflow:
    1. Initialize components (Swarm, ProgramManager, Evaluator)
    2. Execute the Swarm to get proposed changes
    3. Extract rationale and findings from agent messages
    4. Create modified program version
    5. Evaluate the modified program
    6. Return results with program and evaluation
    """

    def __init__(
        self,
        num_iterations: int,
        initial_program_path: str,
        evaluator_path: str,
        output_dir: str,
    ):
        """Initialize the Evolution Orchestrator.

        Args:
            initial_program_path: Path to the initial program with EVOLVE-BLOCKs
            evaluator_path: Path to the evaluator module
            output_dir: Directory for output files (default: creates timestamped dir)

        Raises:
            ValueError: If initial program or evaluator are invalid
            FileNotFoundError: If required files don't exist
        """
        self.num_iterations = num_iterations
        self.initial_program_path = initial_program_path
        self.evaluator_path = evaluator_path
        self.output_dir = Path(output_dir)

        logger.info(
            "Initialized EvolutionOrchestrator: program=%s, evaluator=%s, output=%s",
            initial_program_path,
            evaluator_path,
            output_dir,
        )

    def _setup_output_directory(self, initial_program_name: str) -> None:
        """Create the output directory structure."""
        logger.debug("Setting up output directory structure at %s", self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "programs").mkdir(exist_ok=True)
        (self.output_dir / "conversations").mkdir(exist_ok=True)

        # Copy initial program to programs folder
        import shutil

        dest_path = self.output_dir / "programs" / initial_program_name
        shutil.copy2(self.initial_program_path, dest_path)
        logger.info("Copied initial program to %s", dest_path)

    def run(self):
        """Execute a single evolution using the Swarm.

        Returns:
            EvolutionResults containing the evolved program and evaluation
        """
        logger.info("Starting evolution process")
        start_time = time.time()

        try:
            logger.info("Running evolution with program: %s", self.initial_program_path)

            initial_program_name = f"v00_{Path(self.initial_program_path).name}"
            self._setup_output_directory(initial_program_name)

            # Build context for the Swarm
            context = self._build_evolution_context(initial_program_name)
            logger.debug("Context built with %d characters", len(context))

            # Set up streaming logger for real-time conversation logging
            log_path = self.output_dir / "conversations" / "evolution.txt"
            streaming_logger = StreamingConversationLogger(log_path)

            swarm = self._create_swarm()

            # Set the callback handler on all agents in the swarm
            for node in swarm.nodes.values():
                if hasattr(node, "executor") and hasattr(
                    node.executor, "callback_handler"
                ):
                    node.executor.callback_handler = streaming_logger

            # Execute the Swarm with streaming logger
            logger.info("Executing Swarm (Researcher <-> Supervisor)")
            swarm_result = swarm(context)
            logger.info("Swarm execution completed")

            # Finalize the streaming log
            streaming_logger.finalize()

        except Exception as e:
            logger.exception("Evolution failed: %s", str(e))
            raise

    def _build_evolution_context(self, initial_program_name) -> str:
        """Build context for the Swarm.

        Args:
            program_path: Path to program to evolve

        Returns:
            Formatted context string for the Swarm
        """
        context_parts = []

        # Add program information
        context_parts.append(f"Program to Evolve: {initial_program_name}")
        context_parts.append("")

        # Add task description
        context_parts.append("TASK:")
        context_parts.append(
            "Analyze the program and propose improvements to the EVOLVE-BLOCK sections. "
            "Follow the experimental methodology: form a hypothesis, implement changes, "
            "analyze results, and document findings."
            f"Store successive programs at {self.output_dir}/programs/vXX_<name>, where XX is the version number."
        )

        return "\n".join(context_parts)

    def _create_swarm(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
    ) -> Swarm:
        """Create and configure the Swarm with Researcher and Supervisor agents."""

        researcher = create_researcher_agent(model_id=model_id)
        supervisor = create_supervisor_agent(model_id=model_id)

        return Swarm(
            nodes=[researcher, supervisor],
            entry_point=researcher,
            max_handoffs=self.num_iterations,
            max_iterations=self.num_iterations * 2,
            node_timeout=3600,
        )
