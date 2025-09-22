"""
Document processors for different file types.
"""

from .image_processor import image_processor, ImageProcessor
from .excel_processor import excel_processor, ExcelProcessor
from .text_processor import text_processor, TextProcessor

__all__ = [
    'image_processor',
    'ImageProcessor',
    'excel_processor',
    'ExcelProcessor',
    'text_processor',
    'TextProcessor'
]