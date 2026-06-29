import re

class ContextResolver:
    """Handles Context Hygiene, PII masking, and placeholder resolution."""
    
    def mask_pii(self, text: str) -> str:
        """Redacts emails, common IDs, and names."""
        if not text:
            return text
            
        # Redact emails
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[REDACTED_EMAIL]', text)
        
        # Redact IDs (e.g. 9-digit numbers)
        text = re.sub(r'\b\d{9}\b', '[REDACTED_ID]', text)
        
        # Redact Student Names (simple heuristic: [[STUDENT_NAME]] placeholder)
        text = text.replace('[[STUDENT_NAME]]', '[ANONYMIZED_USER]')
        
        return text

    def resolve(self, text: str) -> str:
        return self.mask_pii(text)
