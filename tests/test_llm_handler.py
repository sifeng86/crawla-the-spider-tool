import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from login.lib.llm_handler import (
    extract_gemini_response_text,
    get_gemini_smart_extraction,
    get_self_healing_format_hint,
    get_llm_thinking_level,
    normalize_llm_output,
    parse_json_output,
    stringify_llm_output,
)


class LlmHandlerTests(unittest.TestCase):
    def test_get_llm_thinking_level_defaults_to_minimal(self):
        self.assertEqual(get_llm_thinking_level({}), 'MINIMAL')

    def test_get_llm_thinking_level_normalizes_custom_value(self):
        self.assertEqual(get_llm_thinking_level({'thinking_level': 'high'}), 'HIGH')

    def test_extract_gemini_response_text_prefers_text_attribute(self):
        response = type('Response', (), {'text': 'Crawla'})()

        self.assertEqual(extract_gemini_response_text(response), 'Crawla')

    def test_stringify_llm_output_handles_list_blocks(self):
        result = [
            {'text': 'Crawla Data Extractor'},
            {'text': 'Secondary text'},
        ]

        self.assertEqual(
            stringify_llm_output(result),
            'Crawla Data Extractor\nSecondary text',
        )

    def test_normalize_llm_output_extracts_final_answer_line(self):
        result = 'Reasoning\nFinal Answer: Crawla Data Extractor'

        self.assertEqual(normalize_llm_output(result), 'Crawla Data Extractor')

    def test_parse_json_output_returns_dict_for_valid_json(self):
        result = '{"title": "Crawla"}'

        self.assertEqual(parse_json_output(result), {'title': 'Crawla'})

    def test_get_self_healing_format_hint_for_id_step(self):
        self.assertEqual(
            get_self_healing_format_hint('find_element_by_id'),
            'Return only the raw id value without a leading #.',
        )

    def test_get_self_healing_format_hint_for_css_step(self):
        self.assertEqual(
            get_self_healing_format_hint('find_element_by_css'),
            'Return a CSS selector string.',
        )

    def test_get_gemini_smart_extraction_returns_structured_json(self):
        with patch('login.lib.llm_handler.get_gemini_response', return_value='{"title": "Crawla"}'):
            result = get_gemini_smart_extraction('{"type":"object"}', '<html></html>')

        self.assertEqual(result, {'title': 'Crawla'})


if __name__ == '__main__':
    unittest.main()