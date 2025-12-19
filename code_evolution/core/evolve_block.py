from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class EvolveBlock:
    """Represents a code block marked for evolution.
    
    Attributes:
        start_line: Line number where the block starts (inclusive).
        end_line: Line number where the block ends (inclusive).
        content: The code content within the block.
        block_id: Identifier for this block (for multiple blocks in one file).
    """
    start_line: int
    end_line: int
    content: str
    block_id: int
    
    def __post_init__(self):
        """Validate block structure."""
        if self.start_line < 0:
            raise ValueError("start_line must be non-negative")
        
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")
        
        if self.block_id < 0:
            raise ValueError("block_id must be non-negative")
