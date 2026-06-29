import os
import re

class SecurityException(Exception):
    pass

class Sanitizer:
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Detects prompt injection attempts in uploaded notes."""
        if not text:
            return text
            
        # Basic signatures
        signatures = [
            "ignore previous instructions",
            "forget all",
            "reveal your system prompt",
            "system prompt",
            "ignore all instructions"
        ]
        
        lower_text = text.lower()
        for sig in signatures:
            if sig in lower_text:
                raise SecurityException(f"Potential prompt injection detected: {sig}")
                
        return text

    @staticmethod
    def sanitize_filename(filepath: str) -> str:
        """Sanitizes file names to prevent path traversal attacks."""
        # Extracts just the base filename, blocking directory escape
        return os.path.basename(filepath)
