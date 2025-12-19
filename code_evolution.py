#!/usr/bin/env python3
"""CLI entry point for the program evolution system.

This script provides the command-line interface for running the
program evolution system. It handles argument parsing, input validation,
orchestrator initialization, and results display.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from code_evolution.orchestrator import EvolutionOrchestrator
from code_evolution.core.program_manager import ProgramManager


def configure_logging():
    """Configure logging based on environment variable.
    
    Supports LOG_LEVEL environment variable with values:
    - DEBUG: Detailed information for debugging
    - INFO: General informational messages (default)
    - WARNING: Warning messages only
    - ERROR: Error messages only
    - CRITICAL: Critical errors only
    """
    # Get log level from environment variable, default to INFO
    log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    # Map string to logging level
    log_level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    log_level = log_level_map.get(log_level_str, logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True  # Override any existing configuration
    )
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.debug("Logging configured with level: %s", log_level_str)


    # turn off low-level logging
    for noisy in ["boto", "boto3", "botocore", "urllib3"]:
        logging.getLogger(noisy).setLevel(logging.ERROR)

# Configure logging before creating logger
configure_logging()
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description='Program Evolution System - Iteratively improve Python programs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python code_evolution.py \\
      --initial-program examples/function_minimization/initial_program.py \\
      --evaluator examples/function_minimization/evaluator.py \\
      --iterations 10 \\
      --output-dir results/run_001

The initial program must contain EVOLVE-BLOCK markers:
  # EVOLVE-BLOCK-START
  # ... code to evolve ...
  # EVOLVE-BLOCK-END

The evaluator must provide an evaluate(program_path: str) function
that returns metrics including 'combined_score'.
        """
    )
    
    parser.add_argument(
        '--initial-program',
        type=str,
        required=True,
        help='Path to the initial Python program with EVOLVE-BLOCK markers'
    )
    
    parser.add_argument(
        '--evaluator',
        type=str,
        required=True,
        help='Path to the evaluator module with evaluate() function'
    )
    
    parser.add_argument(
        '--iterations',
        type=int,
        required=True,
        help='Number of evolution iterations to run'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Directory for output files (default: creates timestamped directory)'
    )
    
    return parser.parse_args()


def validate_file_exists(file_path: str, file_description: str) -> None:
    """Validate that a file exists and is readable.
    
    Args:
        file_path: Path to the file to validate.
        file_description: Human-readable description for error messages.
        
    Raises:
        SystemExit: If the file doesn't exist or isn't readable.
    """
    path = Path(file_path)
    
    if not path.exists():
        logger.error("%s not found: %s", file_description, file_path)
        sys.exit(1)
    
    if not path.is_file():
        logger.error("%s is not a file: %s", file_description, file_path)
        sys.exit(1)
    
    # Try to read the file to ensure it's readable
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.read(1)  # Read just one character to test readability
    except (IOError, OSError, PermissionError) as e:
        logger.error("%s is not readable: %s - %s", file_description, file_path, str(e))
        sys.exit(1)
    
    logger.debug("%s validated: %s", file_description, file_path)


def validate_initial_program(program_path: str) -> None:
    """Validate that the initial program has valid EVOLVE-BLOCK markers.
    
    Args:
        program_path: Path to the program file.
        
    Raises:
        SystemExit: If the program doesn't have valid EVOLVE-BLOCKs.
    """
    program_manager = ProgramManager()

    if not program_manager.validate_program(program_path):
        logger.error(
            "Initial program does not contain valid EVOLVE-BLOCK markers.\n"
            "Programs must have at least one pair of markers:\n"
            "  # EVOLVE-BLOCK-START\n"
            "  # ... code to evolve ...\n"
            "  # EVOLVE-BLOCK-END"
        )
        sys.exit(1)

    # Count the blocks for informational purposes
    try:
        blocks = program_manager.extract_evolve_blocks(program_path)
        logger.info("Found %d EVOLVE-BLOCK(s) in initial program", len(blocks))
    except Exception as e:
        logger.error("Error parsing EVOLVE-BLOCKs: %s", str(e))
        sys.exit(1)


def create_default_output_dir(initial_program_path: str) -> str:
    """Create a default output directory with timestamp in the initial program's folder.

    Args:
        initial_program_path: Path to the initial program file.

    Returns:
        Path to the created output directory.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    program_dir = Path(initial_program_path).parent
    output_dir = str(program_dir / f"evolution_output_{timestamp}")
    logger.info("Using default output directory: %s", output_dir)
    return output_dir


def main():
    """Main entry point for the evolution system."""
    # Parse arguments
    args = parse_arguments()

    logger.info("Starting Program Evolution")
    logger.info("=" * 60)

    # Validate inputs
    logger.info("Validating inputs...")

    validate_file_exists(args.initial_program, "Initial program")
    validate_file_exists(args.evaluator, "Evaluator")
    validate_initial_program(args.initial_program)

    # Create output directory if not provided
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = create_default_output_dir(args.initial_program)

    logger.info("All inputs validated successfully")
    logger.info("=" * 60)

    # Initialize and run the orchestrator
    try:
        logger.info("Initializing Evolution Orchestrator...")
        orchestrator = EvolutionOrchestrator(
            initial_program_path=args.initial_program,
            evaluator_path=args.evaluator,
            num_iterations=args.iterations,
            output_dir=output_dir
        )

        logger.info("Starting evolution process...")
        logger.info("=" * 60)

        orchestrator.run()

        logger.info("Results saved to: %s", output_dir)

        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\nEvolution interrupted by user")
        sys.exit(130)  # Standard exit code for SIGINT

    except Exception as e:
        logger.exception("Evolution failed with error: %s", str(e))
        print("\n" + "=" * 70, file=sys.stderr)
        print("ERROR: Evolution failed", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"\n{str(e)}\n", file=sys.stderr)
        print("Check the logs above for more details.", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
