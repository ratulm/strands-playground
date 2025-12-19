"""Program Manager for code manipulation and EVOLVE-BLOCK handling."""

import logging
import re
from pathlib import Path
from typing import Optional

from .evolve_block import EvolveBlock

logger = logging.getLogger(__name__)


class ProgramManager:
    """Manages program files and EVOLVE-BLOCK operations.
    
    This class handles:
    - Parsing programs to identify EVOLVE-BLOCKs
    - Extracting code from marked sections
    - Replacing EVOLVE-BLOCK content with new implementations
    - Creating versioned program files
    - Validating program structure
    """
    
    BLOCK_START_MARKER = "# EVOLVE-BLOCK-START"
    BLOCK_END_MARKER = "# EVOLVE-BLOCK-END"
    
    def validate_program(self, program_path: str) -> bool:
        """Check if program has valid EVOLVE-BLOCK markers.
        
        Args:
            program_path: Path to the program file to validate.
            
        Returns:
            True if the program contains at least one valid EVOLVE-BLOCK pair,
            False otherwise.
        """
        logger.debug("Validating program: %s", program_path)
        
        try:
            with open(program_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.debug("Read program file: %d characters", len(content))
            
            # Count start and end markers
            start_count = content.count(self.BLOCK_START_MARKER)
            end_count = content.count(self.BLOCK_END_MARKER)
            
            logger.debug("Found %d start markers and %d end markers", start_count, end_count)
            
            # Must have at least one pair and equal counts
            if start_count == 0 or end_count == 0:
                logger.debug("Validation failed: no EVOLVE-BLOCK markers found")
                return False
            
            if start_count != end_count:
                logger.debug("Validation failed: mismatched marker counts")
                return False
            
            # Verify proper nesting (start before end for each pair)
            lines = content.split('\n')
            stack = []
            
            for line in lines:
                if self.BLOCK_START_MARKER in line:
                    stack.append('start')
                elif self.BLOCK_END_MARKER in line:
                    if not stack or stack[-1] != 'start':
                        logger.debug("Validation failed: improper nesting detected")
                        return False
                    stack.pop()
            
            # All blocks should be closed
            is_valid = len(stack) == 0
            
            if is_valid:
                logger.debug("Program validation successful: %d valid EVOLVE-BLOCK(s)", start_count)
            else:
                logger.debug("Validation failed: unclosed EVOLVE-BLOCK(s)")
            
            return is_valid
            
        except (IOError, OSError) as e:
            logger.error("Failed to read program file %s: %s", program_path, str(e))
            return False
    
    def extract_evolve_blocks(self, program_path: str) -> list[EvolveBlock]:
        """Extract all EVOLVE-BLOCK sections from a program.
        
        Args:
            program_path: Path to the program file.
            
        Returns:
            List of EvolveBlock objects, one for each block found.
            
        Raises:
            FileNotFoundError: If program_path doesn't exist.
            ValueError: If the program has invalid EVOLVE-BLOCK structure.
        """
        logger.debug("Extracting EVOLVE-BLOCKs from: %s", program_path)
        
        path = Path(program_path)
        if not path.exists():
            logger.error("Program file not found: %s", program_path)
            raise FileNotFoundError(f"Program file not found: {program_path}")
        
        with open(program_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        logger.debug("Read %d lines from program file", len(lines))
        
        blocks = []
        block_id = 0
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            if self.BLOCK_START_MARKER in line:
                start_line = i
                logger.debug("Found EVOLVE-BLOCK start at line %d", start_line + 1)
                
                # Find the corresponding end marker
                end_line = None
                
                for j in range(i + 1, len(lines)):
                    if self.BLOCK_END_MARKER in lines[j]:
                        end_line = j
                        break
                
                if end_line is None:
                    logger.error("EVOLVE-BLOCK at line %d has no matching end marker", start_line + 1)
                    raise ValueError(
                        f"EVOLVE-BLOCK starting at line {start_line + 1} "
                        f"has no matching end marker"
                    )
                
                logger.debug("Found EVOLVE-BLOCK end at line %d", end_line + 1)
                
                # Extract content between markers (excluding the marker lines)
                content_lines = lines[start_line + 1:end_line]
                content = ''.join(content_lines)
                
                logger.debug("Extracted block %d: %d lines, %d characters", 
                           block_id, len(content_lines), len(content))
                
                blocks.append(EvolveBlock(
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    block_id=block_id
                ))
                
                block_id += 1
                i = end_line + 1
            else:
                i += 1
        
        logger.info("Extracted %d EVOLVE-BLOCK(s) from %s", len(blocks), program_path)
        return blocks
    
    def replace_evolve_blocks(
        self,
        program_path: str,
        blocks: list[EvolveBlock],
        output_path: str
    ) -> None:
        """Replace EVOLVE-BLOCK content and save to output_path.
        
        This method preserves all code outside EVOLVE-BLOCKs, including
        imports, comments, and the marker lines themselves.
        
        Args:
            program_path: Path to the original program file.
            blocks: List of EvolveBlock objects with new content.
            output_path: Path where the modified program should be saved.
            
        Raises:
            FileNotFoundError: If program_path doesn't exist.
            ValueError: If blocks don't match the program structure.
        """
        logger.debug("Replacing EVOLVE-BLOCKs in %s with %d new blocks", program_path, len(blocks))
        
        path = Path(program_path)
        if not path.exists():
            logger.error("Program file not found: %s", program_path)
            raise FileNotFoundError(f"Program file not found: {program_path}")
        
        with open(program_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        logger.debug("Read %d lines from original program", len(lines))
        
        # Extract current blocks to validate structure
        current_blocks = self.extract_evolve_blocks(program_path)
        
        if len(blocks) != len(current_blocks):
            logger.error("Block count mismatch: expected %d, got %d", 
                        len(current_blocks), len(blocks))
            raise ValueError(
                f"Number of blocks mismatch: expected {len(current_blocks)}, "
                f"got {len(blocks)}"
            )
        
        # Sort blocks by block_id to ensure correct replacement order
        sorted_blocks = sorted(blocks, key=lambda b: b.block_id)
        logger.debug("Sorted %d blocks by block_id", len(sorted_blocks))
        
        # Validate block_ids match
        for new_block, current_block in zip(sorted_blocks, current_blocks):
            if new_block.block_id != current_block.block_id:
                logger.error("Block ID mismatch: expected %d, got %d",
                           current_block.block_id, new_block.block_id)
                raise ValueError(
                    f"Block ID mismatch: expected {current_block.block_id}, "
                    f"got {new_block.block_id}"
                )
        
        logger.debug("Block IDs validated successfully")
        
        # Build the new program by replacing block contents
        new_lines = []
        block_idx = 0
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            if self.BLOCK_START_MARKER in line:
                # Keep the start marker
                new_lines.append(line)
                
                # Find the end marker
                end_line = None
                for j in range(i + 1, len(lines)):
                    if self.BLOCK_END_MARKER in lines[j]:
                        end_line = j
                        break
                
                if end_line is None:
                    logger.error("EVOLVE-BLOCK at line %d has no matching end marker", i + 1)
                    raise ValueError(
                        f"EVOLVE-BLOCK starting at line {i + 1} "
                        f"has no matching end marker"
                    )
                
                # Insert the new content
                new_content = sorted_blocks[block_idx].content
                logger.debug("Replacing block %d with %d characters of new content",
                           block_idx, len(new_content))
                
                # Ensure content ends with newline if it doesn't already
                if new_content and not new_content.endswith('\n'):
                    new_content += '\n'
                new_lines.append(new_content)
                
                # Keep the end marker
                new_lines.append(lines[end_line])
                
                block_idx += 1
                i = end_line + 1
            else:
                # Keep all other lines unchanged
                new_lines.append(line)
                i += 1
        
        logger.debug("Built new program with %d lines", len(new_lines))
        
        # Write the modified program
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug("Writing modified program to: %s", output_path)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            logger.info("Successfully wrote modified program to: %s", output_path)
        except IOError as e:
            logger.error("Failed to write modified program to %s: %s", output_path, str(e))
            raise
    
    def create_version(
        self,
        base_program: str,
        modified_blocks: list[EvolveBlock],
        iteration_num: int,
        output_dir: str
    ) -> str:
        """Create a new program version with modifications.
        
        Args:
            base_program: Path to the base program file.
            modified_blocks: List of EvolveBlock objects with new content.
            iteration_num: The iteration number (used in filename).
            output_dir: Directory where the versioned file should be saved.
            
        Returns:
            Path to the newly created program version.
            
        Raises:
            FileNotFoundError: If base_program doesn't exist.
            ValueError: If modified_blocks don't match the program structure.
        """
        logger.debug("Creating version %d from base program: %s", iteration_num, base_program)
        
        if iteration_num < 1:
            logger.error("Invalid iteration_num: %d (must be >= 1)", iteration_num)
            raise ValueError("iteration_num must be >= 1")
        
        # Create output directory if it doesn't exist
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug("Output directory ready: %s", output_dir_path)
        
        # Generate versioned filename
        base_name = Path(base_program).stem
        extension = Path(base_program).suffix
        versioned_filename = f"iteration_{iteration_num:03d}{extension}"
        output_path = output_dir_path / versioned_filename
        
        logger.debug("Generated versioned filename: %s", versioned_filename)
        
        # Replace blocks and save
        self.replace_evolve_blocks(base_program, modified_blocks, str(output_path))
        
        logger.info("Created program version %d: %s", iteration_num, output_path)
        return str(output_path)
