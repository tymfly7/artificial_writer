import os
class FileHandler:
    """Class to handle file operations."""

    @staticmethod
    def save_to_file(filename, content):
        """Save content to a file."""
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(content)

    @staticmethod
    def read_from_file(filename):
        """Read content from a file."""
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as file:
                return file.read()
        else:
            print("File not found.")
            return ""