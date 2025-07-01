import logging

def read_file(file_path):
    """Reads and returns the content of a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()
        return content
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return ""

def write_to_file(file_path, content):
    """Writes content to a file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        logging.debug(f"Wrote '{content}' to {file_path}.")
    except Exception as e:
        logging.error(f"Error writing to file {file_path}: {e}")