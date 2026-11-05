import io
from pathlib import Path
from PIL import Image
from django.conf import settings

MAX_UPLOAD_SIZE = getattr(settings, 'MAX_UPLOAD_SIZE', 5 * 1024 * 1024)
MIN_DIMENSION = getattr(settings, 'MIN_IMAGE_DIMENSION', 64)
MAX_DIMENSION = getattr(settings, 'MAX_IMAGE_DIMENSION', 4096)
ALLOWED_FORMATS = getattr(settings, 'ALLOWED_IMAGE_FORMATS', ['JPEG', 'PNG'])
MIN_BATCH_SIZE = getattr(settings, 'MIN_BATCH_SIZE', 1)
MAX_BATCH_SIZE = getattr(settings, 'MAX_BATCH_SIZE', 10)


def validate_image_file(file_input):
    """
    Validates actual file content, dimensions, and size before inference.
    Accepts decoded JPEG or PNG only, at most 5 MiB, dimensions 64 to 4096 inclusive.
    Returns: (is_valid: bool, error_reason: str, (width, height), format: str)
    """
    # 1. Size check
    file_size = 0
    if hasattr(file_input, 'size'):
        file_size = file_input.size
    elif isinstance(file_input, (str, Path)):
        try:
            file_size = Path(file_input).stat().st_size
        except Exception as e:
            return False, f"File access error: {str(e)}", (0, 0), None
    elif hasattr(file_input, 'seek') and hasattr(file_input, 'tell'):
        pos = file_input.tell()
        file_input.seek(0, io.SEEK_END)
        file_size = file_input.tell()
        file_input.seek(pos)

    if file_size > MAX_UPLOAD_SIZE:
        size_mb = file_size / (1024 * 1024)
        return False, f"File size exceeds 5 MiB limit ({size_mb:.2f} MiB)", (0, 0), None

    if file_size == 0:
        return False, "Uploaded file is completely empty (0 bytes)", (0, 0), None

    # 2. Content & format check with Pillow
    try:
        if isinstance(file_input, (str, Path)):
            with Image.open(file_input) as img:
                img_format = img.format
                width, height = img.size
                img.verify()
        else:
            # File-like object (e.g. Django UploadedFile)
            content = file_input.read()
            if hasattr(file_input, 'seek'):
                file_input.seek(0)
            
            with Image.open(io.BytesIO(content)) as img:
                img_format = img.format
                width, height = img.size
                img.verify()
    except Exception as exc:
        return False, f"Invalid or corrupted image content: {str(exc)}", (0, 0), None

    # 3. Format restriction check (JPEG or PNG only)
    if not img_format or img_format.upper() not in ALLOWED_FORMATS:
        return False, f"Unsupported format '{img_format}'. Only decoded JPEG and PNG images are accepted.", (width, height), img_format

    # 4. Dimension range check (64 to 4096 pixels)
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        return False, f"Dimensions ({width}x{height}) are below minimum required {MIN_DIMENSION}x{MIN_DIMENSION} pixels.", (width, height), img_format

    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        return False, f"Dimensions ({width}x{height}) exceed maximum allowed {MAX_DIMENSION}x{MAX_DIMENSION} pixels.", (width, height), img_format

    return True, "", (width, height), img_format


def validate_batch_size(count):
    """Validates that a batch contains between 1 and 10 files inclusive."""
    if count < MIN_BATCH_SIZE:
        return False, f"Empty batch submitted. A batch must contain at least {MIN_BATCH_SIZE} file."
    if count > MAX_BATCH_SIZE:
        return False, f"Oversized batch ({count} files). A batch must contain at most {MAX_BATCH_SIZE} files."
    return True, ""

