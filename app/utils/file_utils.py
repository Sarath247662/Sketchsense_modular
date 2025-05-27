import os
import uuid
from werkzeug.datastructures import FileStorage

def save_temp_pdf(uploaded_file, folder: str = "static") -> str:
    """
    If given a FileStorage, save it to disk; if given a path string, return it unchanged.

    :param uploaded_file: Either a Werkzeug FileStorage (from request.files) or an existing file path (str)
    :param folder: Destination directory for new uploads
    :return: Path to the PDF on disk
    """
    # If it's already a path, just return it
    if isinstance(uploaded_file, str):
        return uploaded_file

    # Otherwise assume it's FileStorage and save it
    if isinstance(uploaded_file, FileStorage):
        os.makedirs(folder, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}.pdf"
        path = os.path.join(folder, unique_name)
        uploaded_file.save(path)
        return path

    raise ValueError(f"Unsupported type for save_temp_pdf: {type(uploaded_file)}")

def cleanup_temp(path: str) -> None:
    """
    Delete a temporary file if it exists, ignoring errors.

    :param path: File path to remove
    """
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass

