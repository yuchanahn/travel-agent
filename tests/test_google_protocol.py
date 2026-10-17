"""Framing invariants tested with synthetic payloads, without Google requests."""

import unittest

from travel_agent.google_protocol import decode_prog


def envelope(*frames):
    return b")]}'\n" + b"".join(f"{len(frame):x};".encode() + frame for frame in frames) + b"0;"


class ProgTests(unittest.TestCase):
    def test_unicode_frames_use_byte_lengths_and_keep_markup(self):
        markup = '<div>한국어</div>'.encode()
        document, metadata = decode_prog(envelope(b'["control"]', markup))
        self.assertIn(markup, document)
        self.assertNotIn(b'control', document)
        self.assertEqual(metadata, {"protocol_frame_count": 3, "markup_frame_count": 1})

    def test_script_source_is_not_reinterpreted_as_embedded_html(self):
        document, _ = decode_prog(envelope(b'var source="<a href=bad>fake</a>";'))
        self.assertNotIn(b"fake", document)

    def test_truncated_invalid_or_unterminated_data_is_rejected(self):
        for data in [b")]}'\nff;<div>", b")]}'\nzz;bad0;", b")]}'\n3;abc", envelope(b'<div/>')+b'extra']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_prog(data)

    def test_character_length_cannot_be_substituted_for_byte_length(self):
        markup = '<div>한글</div>'
        wrong = b")]}'\n" + f"{len(markup):x};".encode() + markup.encode() + b"0;"
        with self.assertRaises(ValueError):
            decode_prog(wrong)


if __name__ == "__main__":
    unittest.main()
