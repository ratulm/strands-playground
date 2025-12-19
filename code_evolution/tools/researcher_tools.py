"""Tool functions for the Researcher Agent.

This module provides tools that enable the Researcher Agent to:
- Read and write program files
- Execute shell commands for experiments
- Parse and manipulate EVOLVE-BLOCKs in programs
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

import strands
from ..core.program_manager import ProgramManager
from ..core.evolve_block import EvolveBlock
from ..tools.evaluator import Evaluator, EvaluatorConfig

logger = logging.getLogger(__name__)

# Initialize a shared ProgramManager instance
_program_manager = ProgramManager()

# Initialize a shared Evaluator instance (will be set when evaluate_program is first called)
_evaluator: Optional[Evaluator] = None


@strands.tool
def read_file(file_path: str) -> str:
    """Read the contents of a file.
    
    Use this tool to inspect program files, read code, or examine any text file
    in the working directory.
    
    Args:
        file_path: Path to the file to read (relative or absolute).
        
    Returns:
        The contents of the file as a string.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
        IOError: If the file cannot be read.
    """
    logger.debug("Tool read_file called with file_path: %s", file_path)
    
    try:
        path = Path(file_path)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.debug("Successfully read %d characters from %s", len(content), file_path)
        return content
    except FileNotFoundError:
        logger.warning("File not found: %s", file_path)
        return f"Error: File not found: {file_path}"
    except IOError as e:
        logger.error("IO error reading file %s: %s", file_path, str(e))
        return f"Error reading file {file_path}: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error reading file %s", file_path)
        return f"Unexpected error reading file {file_path}: {str(e)}"


@strands.tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file, creating it if it doesn't exist.
    
    Use this tool to create modified program versions or save experimental code.
    The parent directory will be created if it doesn't exist.
    
    Args:
        file_path: Path where the file should be written (relative or absolute).
        content: The text content to write to the file.
        
    Returns:
        A success message with the file path, or an error message.
    """
    logger.debug("Tool write_file called with file_path: %s, content length: %d", 
                file_path, len(content))
    
    try:
        path = Path(file_path)
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("Successfully wrote %d characters to %s", len(content), file_path)
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except IOError as e:
        logger.error("IO error writing to file %s: %s", file_path, str(e))
        return f"Error writing to file {file_path}: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error writing to file %s", file_path)
        return f"Unexpected error writing to file {file_path}: {str(e)}"


@strands.tool
def execute_shell(command: str, timeout: Optional[int] = 30) -> str:
    """Execute a shell command and capture its output.
    
    Use this tool to run experiments, execute programs, or perform system operations.
    Both stdout and stderr are captured and returned.
    
    Args:
        command: The shell command to execute.
        timeout: Maximum time in seconds to wait for command completion (default: 30).
        
    Returns:
        A string containing the command output (stdout and stderr combined),
        or an error message if the command fails.
    """
    logger.debug("Tool execute_shell called with command: %s, timeout: %d", command, timeout)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        logger.debug("Command completed with return code: %d", result.returncode)
        
        # Combine stdout and stderr
        output = ""
        if result.stdout:
            output += "STDOUT:\n" + result.stdout
            logger.debug("Captured stdout: %d characters", len(result.stdout))
        if result.stderr:
            if output:
                output += "\n\n"
            output += "STDERR:\n" + result.stderr
            logger.debug("Captured stderr: %d characters", len(result.stderr))
        
        # Include return code information
        if result.returncode != 0:
            output = f"Command exited with code {result.returncode}\n\n" + output
            logger.warning("Command failed with return code: %d", result.returncode)
        else:
            logger.info("Command executed successfully")
        
        return output if output else "Command completed with no output"
        
    except subprocess.TimeoutExpired:
        logger.error("Command timed out after %d seconds: %s", timeout, command)
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        logger.exception("Error executing command: %s", command)
        return f"Error executing command: {str(e)}"


@strands.tool
def parse_evolve_blocks(program_path: str) -> str:
    """Extract EVOLVE-BLOCK sections from a program file.
    
    Use this tool to identify which code sections can be modified in a program.
    Returns information about each EVOLVE-BLOCK including its location and content.
    
    Args:
        program_path: Path to the program file to parse.
        
    Returns:
        A formatted string describing each EVOLVE-BLOCK found, including:
        - Block ID
        - Line numbers (start and end)
        - The code content within the block
    """
    try:
        blocks = _program_manager.extract_evolve_blocks(program_path)
        
        if not blocks:
            return f"No EVOLVE-BLOCKs found in {program_path}"
        
        result = f"Found {len(blocks)} EVOLVE-BLOCK(s) in {program_path}:\n\n"
        
        for block in blocks:
            result += f"Block ID: {block.block_id}\n"
            result += f"Lines: {block.start_line + 1} to {block.end_line + 1}\n"
            result += f"Content:\n{block.content}\n"
            result += "-" * 60 + "\n\n"
        
        return result
        
    except FileNotFoundError:
        return f"Error: File not found: {program_path}"
    except ValueError as e:
        return f"Error parsing EVOLVE-BLOCKs: {str(e)}"
    except Exception as e:
        return f"Unexpected error parsing {program_path}: {str(e)}"


@strands.tool
def replace_evolve_blocks(
    program_path: str,
    output_path: str,
    block_modifications: str
) -> str:
    """Replace EVOLVE-BLOCK content in a program and save to a new file.
    
    Use this tool to create a modified version of a program with new code in the
    EVOLVE-BLOCKs. All code outside the blocks is preserved exactly.
    
    The block_modifications parameter should be formatted as:
    
    BLOCK_ID: <id>
    <new code content>
    ---
    BLOCK_ID: <id>
    <new code content>
    ---
    
    Args:
        program_path: Path to the original program file.
        output_path: Path where the modified program should be saved.
        block_modifications: A formatted string specifying the new content for each block.
        
    Returns:
        A success message with the output path, or an error message.
    """
    try:
        # Parse the block_modifications string
        blocks_to_replace = []

        # Split by separator
        sections = block_modifications.strip().split('---')

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Extract block ID and content
            lines = section.split('\n', 1)
            if len(lines) < 2:
                return f"Error: Invalid block modification format. Expected 'BLOCK_ID: <id>' followed by content."

            header = lines[0].strip()
            if not header.startswith('BLOCK_ID:'):
                return f"Error: Expected 'BLOCK_ID: <id>' but got: {header}"

            try:
                block_id = int(header.split(':', 1)[1].strip())
            except (ValueError, IndexError):
                return f"Error: Invalid block ID in: {header}"

            content = lines[1] if len(lines) > 1 else ""

            # Get the original block to preserve line numbers
            original_blocks = _program_manager.extract_evolve_blocks(program_path)

            # Find the matching original block
            original_block = None
            for orig in original_blocks:
                if orig.block_id == block_id:
                    original_block = orig
                    break

            if original_block is None:
                return f"Error: Block ID {block_id} not found in {program_path}"

            # Create new block with updated content but original line numbers
            new_block = EvolveBlock(
                start_line=original_block.start_line,
                end_line=original_block.end_line,
                content=content,
                block_id=block_id
            )
            blocks_to_replace.append(new_block)

        if not blocks_to_replace:
            return "Error: No valid block modifications found in the input"

        # Perform the replacement
        _program_manager.replace_evolve_blocks(
            program_path,
            blocks_to_replace,
            output_path
        )

        return f"Successfully created modified program at {output_path} with {len(blocks_to_replace)} block(s) updated"

    except FileNotFoundError:
        return f"Error: File not found: {program_path}"
    except ValueError as e:
        return f"Error replacing blocks: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@strands.tool
def evaluate_program(
    program_path: str, evaluation_file: str, timeout: Optional[int] = 60
) -> str:
    """Evaluate a program using the specified evaluation file.

    Use this tool to measure the performance and quality of a program.
    The evaluation file should contain an 'evaluate' function that takes
    a program path and returns metrics.

    Args:
        program_path: Path to the program file to evaluate.
        evaluation_file: Path to the evaluation module (Python file with 'evaluate' function).
        timeout: Maximum time in seconds to wait for evaluation (default: 60).

    Returns:
        A formatted string containing the evaluation metrics, or an error message.
    """
    global _evaluator

    logger.debug(
        "Tool evaluate_program called with program_path: %s, evaluation_file: %s, timeout: %d",
        program_path,
        evaluation_file,
        timeout,
    )

    try:
        # Check if program file exists
        if not Path(program_path).exists():
            return f"Error: Program file not found: {program_path}"

        # Check if evaluation file exists
        if not Path(evaluation_file).exists():
            return f"Error: Evaluation file not found: {evaluation_file}"

        # Initialize or reinitialize evaluator if needed
        config = EvaluatorConfig(timeout=timeout, max_retries=1)
        _evaluator = Evaluator(config=config, evaluation_file=evaluation_file)

        logger.info("Starting evaluation of %s", program_path)

        # Read the program code
        with open(program_path, "r", encoding="utf-8") as f:
            program_code = f.read()

        # Run evaluation (this is async, so we need to handle it)
        import asyncio

        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task
            result = asyncio.create_task(
                _evaluator.evaluate_program(program_code, program_path)
            )
            # This won't work in sync context, so we need to use run_until_complete
            # But we can't do that in an existing loop, so we'll use a different approach
            logger.warning(
                "Running in async context, evaluation may not complete immediately"
            )
            return "Error: evaluate_program tool cannot be called from async context. Use execute_shell to run evaluation script instead."
        except RuntimeError:
            # No event loop running, we can create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    _evaluator.evaluate_program(program_code, program_path)
                )
            finally:
                loop.close()

        # Format the results
        output = f"Evaluation Results for {program_path}:\n"
        output += "=" * 60 + "\n\n"

        # Display metrics
        output += "Metrics:\n"
        for metric_name, metric_value in result.metrics.items():
            if isinstance(metric_value, float):
                output += f"  {metric_name}: {metric_value:.4f}\n"
            else:
                output += f"  {metric_name}: {metric_value}\n"

        # Display stdout if present
        if result.stdout:
            output += "\nProgram Output (stdout):\n"
            output += "-" * 60 + "\n"
            output += result.stdout
            output += "\n"

        # Display stderr if present
        if result.stderr:
            output += "\nProgram Errors (stderr):\n"
            output += "-" * 60 + "\n"
            output += result.stderr
            output += "\n"

        # Display artifacts if present
        if result.has_artifacts():
            output += "\nArtifacts:\n"
            for key in result.get_artifact_keys():
                size = result.get_artifact_size(key)
                output += f"  {key}: {size} bytes\n"

        # Write output to file in the same folder as program_path
        program_path_obj = Path(program_path)
        output_file = (
            program_path_obj.parent / f"{program_path_obj.stem}_evaluation.txt"
        )

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
            logger.info("Evaluation results written to %s", output_file)
            output += f"\n{'=' * 60}\n"
            output += f"Results saved to: {output_file}\n"
        except IOError as e:
            logger.error("Failed to write evaluation results to file: %s", str(e))
            output += f"\nWarning: Could not save results to file: {str(e)}\n"

        logger.info("Evaluation completed successfully")
        return output

    except Exception as e:
        logger.exception("Error evaluating program %s", program_path)
        return f"Error evaluating program: {str(e)}"
