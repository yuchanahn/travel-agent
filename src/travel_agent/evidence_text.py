"""Verbatim evidence boundaries and explicit, non-semantic layout warnings."""
import re


def body_signal(text):
    """Warn about menu-like layouts; never infer factual quality from layout."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    short = [line for line in lines if len(line) < 35]
    if (len(lines) >= 12 and len(short) / len(lines) >= .9
            and sum(map(len,short)) / max(1,sum(map(len,lines))) >= .8):
        return 'navigation_heavy'
    return 'text_extracted'


def units(text):
    """Preserve paragraphs where possible, splitting long ones at sentence/line ends."""
    for paragraph in re.split(r'\n\s*\n', text):
        paragraph = paragraph.strip()
        if paragraph:
            yield paragraph


def bounded_blocks(text, max_chars, max_bytes=None):
    def fits(value):
        return len(value) <= max_chars and (max_bytes is None or len(value.encode()) <= max_bytes)

    blocks, current = [], ''
    for paragraph in units(text):
        # Only break a paragraph when it cannot fit. This keeps headings,
        # addresses and itinerary lists intact under the available budget.
        pieces = [paragraph] if fits(paragraph) else re.split(r'(?<=[.!?。！？])\s+|\n', paragraph)
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if not fits(piece):
                # An oversized indivisible sentence is omitted, not silently
                # sliced into an apparent complete statement.
                if current:
                    blocks.append(current)
                    current = ''
                continue
            trial = current + ('\n\n' if current else '') + piece
            if current and not fits(trial):
                blocks.append(current)
                current = ''
            current += ('\n\n' if current else '') + piece
    if current:
        blocks.append(current)
    return blocks


def bounded_prefix(text, max_bytes):
    """Prefer a complete sentence/line; otherwise stop before a complete word."""
    if len(text.encode()) <= max_bytes:
        return text
    prefix = text.encode()[:max_bytes].decode('utf-8', errors='ignore')
    boundaries = [match for match in re.finditer(r'[.!?。！？](?=\s|$)|\n', text)
                  if match.end() <= len(prefix)]
    if boundaries:
        return prefix[:boundaries[-1].end()].rstrip()
    # If byte clipping ended in a word, drop that incomplete word. A very
    # long unbroken token returns empty instead of a misleading fragment.
    if len(prefix) < len(text) and not text[len(prefix)].isspace():
        prefix = re.sub(r'\s*\S+$', '', prefix)
    return prefix.rstrip()
