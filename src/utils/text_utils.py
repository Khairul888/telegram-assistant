"""
Text processing utilities for Telegram Assistant.
Provides text manipulation, cleaning, and analysis functions.
"""

import re
import string
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import unicodedata

from ..core.config import settings
from ..core.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# TEXT CLEANING AND NORMALIZATION
# =============================================================================

def clean_text(text: str, remove_extra_whitespace: bool = True) -> str:
    """
    Clean and normalize text content.

    Args:
        text: Input text to clean
        remove_extra_whitespace: Whether to remove extra whitespace

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)

    # Remove control characters except tab, newline, and carriage return
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\t\n\r')

    if remove_extra_whitespace:
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()

    return text


def remove_html_tags(text: str) -> str:
    """
    Remove HTML tags from text.

    Args:
        text: Text with HTML tags

    Returns:
        Text without HTML tags
    """
    if not text:
        return ""

    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)

    # Decode HTML entities
    html_entities = {
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' '
    }

    for entity, char in html_entities.items():
        text = text.replace(entity, char)

    return text


def remove_urls(text: str, replacement: str = '') -> str:
    """
    Remove URLs from text.

    Args:
        text: Input text
        replacement: Text to replace URLs with

    Returns:
        Text without URLs
    """
    if not text:
        return ""

    # URL pattern
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )

    return url_pattern.sub(replacement, text)


def remove_emails(text: str, replacement: str = '') -> str:
    """
    Remove email addresses from text.

    Args:
        text: Input text
        replacement: Text to replace emails with

    Returns:
        Text without email addresses
    """
    if not text:
        return ""

    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    return email_pattern.sub(replacement, text)


def remove_phone_numbers(text: str, replacement: str = '') -> str:
    """
    Remove phone numbers from text.

    Args:
        text: Input text
        replacement: Text to replace phone numbers with

    Returns:
        Text without phone numbers
    """
    if not text:
        return ""

    # Various phone number patterns
    phone_patterns = [
        r'\+?1?\d{9,15}',
        r'\(\d{3}\)\s*\d{3}-\d{4}',
        r'\d{3}-\d{3}-\d{4}',
        r'\d{3}\.\d{3}\.\d{4}'
    ]

    for pattern in phone_patterns:
        text = re.sub(pattern, replacement, text)

    return text


# =============================================================================
# TEXT CHUNKING AND SPLITTING
# =============================================================================

def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    separator: str = "\n\n"
) -> List[str]:
    """
    Split text into chunks with overlap.

    Args:
        text: Text to chunk
        chunk_size: Maximum chunk size in characters
        chunk_overlap: Number of characters to overlap between chunks
        separator: Primary separator to use for splitting

    Returns:
        List of text chunks
    """
    if not text:
        return []

    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    if len(text) <= chunk_size:
        return [text]

    chunks = []

    # First, try to split on the separator
    parts = text.split(separator)
    current_chunk = ""

    for part in parts:
        # If adding this part would exceed chunk size
        if len(current_chunk) + len(part) + len(separator) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())

                # Start new chunk with overlap
                if chunk_overlap > 0:
                    overlap_text = current_chunk[-chunk_overlap:]
                    current_chunk = overlap_text + separator + part
                else:
                    current_chunk = part
            else:
                # Part is too large, need to split it further
                current_chunk = part
        else:
            if current_chunk:
                current_chunk += separator + part
            else:
                current_chunk = part

    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    # If chunks are still too large, split them further
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > chunk_size:
            # Split by sentences, then by words if needed
            sub_chunks = _split_large_chunk(chunk, chunk_size, chunk_overlap)
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(chunk)

    return [chunk for chunk in final_chunks if chunk.strip()]


def _split_large_chunk(text: str, max_size: int, overlap: int) -> List[str]:
    """Split a large chunk into smaller pieces."""
    chunks = []

    # Try splitting by sentences first
    sentences = re.split(r'[.!?]+', text)
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(current_chunk) + len(sentence) + 1 > max_size:
            if current_chunk:
                chunks.append(current_chunk.strip())

                # Add overlap
                if overlap > 0:
                    overlap_text = current_chunk[-overlap:]
                    current_chunk = overlap_text + " " + sentence
                else:
                    current_chunk = sentence
            else:
                # Sentence is too large, split by words
                word_chunks = _split_by_words(sentence, max_size, overlap)
                chunks.extend(word_chunks)
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def _split_by_words(text: str, max_size: int, overlap: int) -> List[str]:
    """Split text by words when sentences are too large."""
    words = text.split()
    chunks = []
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) + 1 > max_size:
            if current_chunk:
                chunks.append(current_chunk.strip())

                # Add overlap
                if overlap > 0:
                    overlap_words = current_chunk.split()[-overlap//10:]  # Rough word overlap
                    current_chunk = " ".join(overlap_words) + " " + word
                else:
                    current_chunk = word
            else:
                # Single word is too large - just add it
                chunks.append(word)
        else:
            if current_chunk:
                current_chunk += " " + word
            else:
                current_chunk = word

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# =============================================================================
# TEXT ANALYSIS
# =============================================================================

def count_tokens_approximate(text: str, avg_chars_per_token: float = 4.0) -> int:
    """
    Approximate token count for text.

    Args:
        text: Input text
        avg_chars_per_token: Average characters per token

    Returns:
        Approximate token count
    """
    if not text:
        return 0

    # Remove extra whitespace and count characters
    clean_text = re.sub(r'\s+', ' ', text.strip())
    return max(1, int(len(clean_text) / avg_chars_per_token))


def count_words(text: str) -> int:
    """
    Count words in text.

    Args:
        text: Input text

    Returns:
        Word count
    """
    if not text:
        return 0

    # Split by whitespace and filter out empty strings
    words = [word for word in text.split() if word.strip()]
    return len(words)


def count_sentences(text: str) -> int:
    """
    Count sentences in text.

    Args:
        text: Input text

    Returns:
        Sentence count
    """
    if not text:
        return 0

    # Split by sentence terminators
    sentences = re.split(r'[.!?]+', text)
    # Filter out empty sentences
    sentences = [s for s in sentences if s.strip()]
    return len(sentences)


def get_text_stats(text: str) -> Dict[str, Any]:
    """
    Get comprehensive text statistics.

    Args:
        text: Input text

    Returns:
        Dictionary with text statistics
    """
    if not text:
        return {
            "character_count": 0,
            "word_count": 0,
            "sentence_count": 0,
            "paragraph_count": 0,
            "token_count_approx": 0,
            "avg_words_per_sentence": 0,
            "avg_chars_per_word": 0
        }

    character_count = len(text)
    word_count = count_words(text)
    sentence_count = count_sentences(text)
    paragraph_count = len([p for p in text.split('\n\n') if p.strip()])
    token_count = count_tokens_approximate(text)

    return {
        "character_count": character_count,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "token_count_approx": token_count,
        "avg_words_per_sentence": word_count / max(1, sentence_count),
        "avg_chars_per_word": character_count / max(1, word_count)
    }


# =============================================================================
# TEXT EXTRACTION AND KEYWORDS
# =============================================================================

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extract potential keywords from text (simple implementation).

    Args:
        text: Input text
        max_keywords: Maximum number of keywords to return

    Returns:
        List of keywords
    """
    if not text:
        return []

    # Clean text
    text = clean_text(text.lower())

    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))

    # Common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'
    }

    # Extract words and count frequency
    words = text.split()
    word_freq = {}

    for word in words:
        if len(word) > 2 and word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1

    # Sort by frequency and return top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in sorted_words[:max_keywords]]


def extract_phrases(text: str, min_length: int = 2, max_length: int = 4) -> List[str]:
    """
    Extract phrases (n-grams) from text.

    Args:
        text: Input text
        min_length: Minimum phrase length in words
        max_length: Maximum phrase length in words

    Returns:
        List of phrases
    """
    if not text:
        return []

    # Clean and tokenize
    text = clean_text(text.lower())
    words = text.split()

    if len(words) < min_length:
        return []

    phrases = []

    for n in range(min_length, max_length + 1):
        for i in range(len(words) - n + 1):
            phrase = ' '.join(words[i:i + n])
            if len(phrase.strip()) > 0:
                phrases.append(phrase)

    return phrases


# =============================================================================
# TEXT FORMATTING
# =============================================================================

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Input text
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    # Try to truncate at word boundary
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')

    if last_space > max_length * 0.7:  # If we can truncate at word boundary without losing too much
        truncated = truncated[:last_space]

    return truncated + suffix


def format_text_preview(text: str, max_length: int = 150) -> str:
    """
    Create a preview of text content.

    Args:
        text: Input text
        max_length: Maximum preview length

    Returns:
        Text preview
    """
    if not text:
        return ""

    # Clean the text
    preview = clean_text(text)

    # Remove extra line breaks
    preview = re.sub(r'\n+', ' ', preview)

    # Truncate if needed
    if len(preview) > max_length:
        preview = truncate_text(preview, max_length)

    return preview


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    Args:
        text: Input text

    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""

    # Replace multiple whitespace characters with single space
    text = re.sub(r'\s+', ' ', text)

    # Replace multiple line breaks with double line break
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

    return text.strip()


# =============================================================================
# LANGUAGE DETECTION (Basic)
# =============================================================================

def detect_language_simple(text: str) -> Optional[str]:
    """
    Simple language detection based on character patterns.

    Args:
        text: Input text

    Returns:
        Language code (en, es, fr, etc.) or None
    """
    if not text or len(text) < 50:
        return None

    # Common words in different languages
    language_indicators = {
        'en': ['the', 'and', 'you', 'that', 'was', 'for', 'are', 'with', 'his', 'they'],
        'es': ['que', 'de', 'no', 'la', 'el', 'en', 'es', 'se', 'lo', 'le'],
        'fr': ['de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que'],
        'de': ['der', 'die', 'und', 'in', 'den', 'von', 'zu', 'das', 'mit', 'sich'],
    }

    text_lower = text.lower()
    scores = {}

    for lang, indicators in language_indicators.items():
        score = sum(1 for word in indicators if f' {word} ' in text_lower)
        scores[lang] = score

    if scores:
        max_lang = max(scores, key=scores.get)
        if scores[max_lang] > 2:  # Minimum threshold
            return max_lang

    return 'en'  # Default to English


# =============================================================================
# TEXT VALIDATION
# =============================================================================

def is_meaningful_text(text: str, min_words: int = 3) -> bool:
    """
    Check if text contains meaningful content.

    Args:
        text: Input text
        min_words: Minimum number of words required

    Returns:
        True if text is meaningful
    """
    if not text:
        return False

    # Clean text
    clean = clean_text(text)

    # Check word count
    word_count = count_words(clean)
    if word_count < min_words:
        return False

    # Check if it's not just punctuation or numbers
    alphanumeric_chars = sum(1 for c in clean if c.isalnum())
    if alphanumeric_chars < len(clean) * 0.3:  # At least 30% alphanumeric
        return False

    return True


def contains_sensitive_info(text: str) -> Dict[str, bool]:
    """
    Check if text contains potentially sensitive information.

    Args:
        text: Input text

    Returns:
        Dictionary with sensitivity checks
    """
    if not text:
        return {"has_email": False, "has_phone": False, "has_ssn": False, "has_credit_card": False}

    # Email pattern
    has_email = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text))

    # Phone pattern (various formats)
    has_phone = bool(re.search(r'(\+?1?\d{9,15}|\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4})', text))

    # SSN pattern
    has_ssn = bool(re.search(r'\b\d{3}-\d{2}-\d{4}\b', text))

    # Credit card pattern (basic)
    has_credit_card = bool(re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', text))

    return {
        "has_email": has_email,
        "has_phone": has_phone,
        "has_ssn": has_ssn,
        "has_credit_card": has_credit_card
    }


if __name__ == "__main__":
    # Test text utilities
    sample_text = """
    This is a sample text with multiple sentences. It contains some URLs like https://example.com
    and email addresses like user@example.com. The text also has   extra   whitespace   that
    should be cleaned up.


    This is a new paragraph with more content for testing.
    """

    print("Original text:")
    print(repr(sample_text))
    print("\nCleaned text:")
    print(repr(clean_text(sample_text)))
    print("\nText stats:")
    print(get_text_stats(sample_text))
    print("\nKeywords:")
    print(extract_keywords(sample_text))
    print("\nSensitive info check:")
    print(contains_sensitive_info(sample_text))