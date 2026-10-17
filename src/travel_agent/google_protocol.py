"""Decode the observed Google prog framing without executing response scripts."""

import re


def decode_prog(body):
    """Return HTML frames and non-sensitive structure diagnostics.

    Lengths are hexadecimal byte counts, not Python character counts. Only
    actual markup frames are passed to an HTML parser; control/script data is
    never evaluated as JavaScript or interpreted as a source of credentials.
    """
    if not isinstance(body, bytes) or not body.startswith(b")]}'\n") or len(body) > 4_000_000:
        raise ValueError("Unsupported Google prog envelope")
    position, frames, markup = 5, 0, []
    ended = False
    while position < len(body):
        if frames >= 256:
            raise ValueError("Too many Google prog frames")
        prefix = re.match(rb"([0-9a-fA-F]{1,8});", body[position:])
        if not prefix:
            raise ValueError("Unknown Google prog frame prefix")
        size = int(prefix[1], 16)
        position += prefix.end()
        if position + size > len(body):
            raise ValueError("Truncated Google prog frame")
        frame = body[position:position+size]
        position += size
        frames += 1
        if not size:
            if body[position:].strip():
                raise ValueError("Unexpected data after Google prog end")
            ended = True
            break
        if frame.lstrip().startswith(b"<"):
            markup.append(frame)
    if not ended:
        raise ValueError("Missing Google prog end marker")
    return b"<html><body>" + b"".join(markup) + b"</body></html>", {
        "protocol_frame_count": frames, "markup_frame_count": len(markup)}
