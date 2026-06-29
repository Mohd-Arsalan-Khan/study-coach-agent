import os

class SecurityEnforcer:
    def __init__(self, notes_dir: str, progress_file: str):
        self.notes_dir = os.path.abspath(notes_dir)
        self.progress_file = os.path.abspath(progress_file)
        
    def validate_read(self, filepath: str) -> str:
        """Ensures the file is within the notes directory."""
        abs_path = os.path.abspath(filepath)
        if not abs_path.startswith(self.notes_dir):
            raise PermissionError(f"Access denied: Read operations restricted to {self.notes_dir}")
        return abs_path
        
    def validate_write(self, filepath: str) -> str:
        """Ensures write access is explicitly for progress.json."""
        abs_path = os.path.abspath(filepath)
        if abs_path != self.progress_file:
            raise PermissionError(f"Access denied: Write operations restricted to {self.progress_file}")
        return abs_path
