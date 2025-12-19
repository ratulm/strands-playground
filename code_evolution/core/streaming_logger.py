"""Streaming logger for real-time conversation logging."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StreamingConversationLogger:
    """Callback handler that streams conversation events to a log file in real-time.
    
    This is a callable class that can be passed as a callback to Strands agents.
    """
    
    def __init__(self, log_path: Path):
        """Initialize the streaming logger.
        
        Args:
            log_path: Path to the log file to write to.
        """
        self.log_path = log_path
        self.message_count = 0
        self._file_handle: Optional[object] = None
        self._current_tool_use_id: Optional[str] = None
        self._logged_tool_uses: set = set()
        self._logged_tool_results: set = set()
        
        # Initialize the log file with header
        self._initialize_log()
    
    def __call__(self, **kwargs: Any) -> None:
        """Handle callback events from the agent.
        
        Args:
            **kwargs: Event data from the agent.
        """
        # Handle different event types
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use", {})
        reasoningText = kwargs.get("reasoningText", "")
        
        # Check for tool result events
        if "tool_result" in kwargs:
            tool_result = kwargs["tool_result"]
            tool_use_id = tool_result.get("toolUseId", "")
            
            # Only log if we haven't logged this result yet
            if tool_use_id and tool_use_id not in self._logged_tool_results:
                self._logged_tool_results.add(tool_use_id)
                
                status = tool_result.get("status", "unknown")
                content_items = tool_result.get("content", [])
                
                self._append_to_log(f"\n{'─' * 80}\n")
                if status == "success":
                    self._append_to_log(f"✓ TOOL RESULT (success)\n")
                else:
                    self._append_to_log(f"❌ TOOL RESULT (error)\n")
                self._append_to_log(f"{'─' * 80}\n")
                
                # Log the result content
                for item in content_items:
                    if isinstance(item, dict) and 'text' in item:
                        result_text = item['text']
                        # Truncate very long results
                        if len(result_text) > 1000:
                            result_text = result_text[:1000] + "\n... (truncated)"
                        self._append_to_log(f"{result_text}\n")
                
                self._append_to_log("\n")
        
        # Stream reasoning text
        if reasoningText:
            self._append_to_log(f"💭 {reasoningText}\n")
        
        # Stream regular text
        if data:
            self._append_to_log(data)
            if complete:
                self._append_to_log("\n")
        
        # Log tool usage (only once per tool use)
        if current_tool_use and current_tool_use.get("name"):
            tool_use_id = current_tool_use.get("toolUseId", "")
            
            # Only log if this is a new tool use we haven't seen
            if tool_use_id and tool_use_id not in self._logged_tool_uses:
                self._logged_tool_uses.add(tool_use_id)
                
                tool_name = current_tool_use.get("name", "unknown")
                # Try different possible keys for input
                tool_input = current_tool_use.get("input") or current_tool_use.get("toolInput") or {}
                
                self._append_to_log(f"\n{'─' * 80}\n")
                self._append_to_log(f"🔧 TOOL USE: {tool_name}\n")
                self._append_to_log(f"{'─' * 80}\n")
                
                if tool_input and isinstance(tool_input, dict):
                    self._append_to_log("Parameters:\n")
                    # Format each parameter on its own line for readability
                    for key, value in tool_input.items():
                        # Truncate long values
                        value_str = str(value)
                        if len(value_str) > 200:
                            value_str = value_str[:200] + "... (truncated)"
                        self._append_to_log(f"  • {key}: {value_str}\n")
                elif tool_input:
                    # If input exists but isn't a dict, show it as-is
                    self._append_to_log(f"Parameters: {tool_input}\n")
                else:
                    self._append_to_log("  (no parameters)\n")
                
                self._append_to_log("\n")
    
    def _initialize_log(self):
        """Create the log file and write the header."""
        try:
            with open(self.log_path, 'w') as f:
                f.write(f"╔{'═' * 78}╗\n")
                f.write(f"║ STREAMING CONVERSATION LOG{' ' * 51}║\n")
                f.write(f"╚{'═' * 78}╝\n\n")
                f.write("🔴 LIVE - Messages will appear as they are generated\n\n")
            logger.debug("Initialized streaming log at: %s", self.log_path)
        except IOError as e:
            logger.error("Failed to initialize streaming log: %s", str(e))
    
    def _append_to_log(self, text: str):
        """Append text to the log file.
        
        Args:
            text: Text to append.
        """
        try:
            with open(self.log_path, 'a') as f:
                f.write(text)
                f.flush()  # Ensure immediate write
        except IOError as e:
            logger.error("Failed to append to streaming log: %s", str(e))
    

    
    def finalize(self):
        """Finalize the log file."""
        text = f"\n{'═' * 80}\n"
        text += "END OF CONVERSATION\n"
        self._append_to_log(text)
        logger.debug("Finalized streaming log")
