import unittest
from fractions import Fraction

from matching.wolfram import WolframLiteralError, parse_wolfram_literal


class WolframLiteralTests(unittest.TestCase):
    def test_exact_rationals_nested_lists_and_comments(self):
        result = parse_wolfram_literal(
            '(* outer (* nested *) *) {{{1,0},{1},-11/6},"F","C",1}')
        self.assertEqual(result, [[[1, 0], [1], Fraction(-11, 6)], "F", "C", 1])

    def test_string_escapes_and_wrapped_source(self):
        text = '{"a\\\\b\\n\\\"c", "long' + "\\\n" + 'label"}'
        self.assertEqual(parse_wolfram_literal(text), ['a\\b\n"c', "longlabel"])

    def test_empty_list_and_comments_inside_strings(self):
        self.assertEqual(parse_wolfram_literal('{{}, "(* literal *)"}'),
                         [[], "(* literal *)"])

    def test_rejects_executable_wolfram_and_trailing_statements(self):
        for text in ('Get["secret"]', '{1};Run["command"]', '__import__("os")'):
            with self.subTest(text=text), self.assertRaises(WolframLiteralError):
                parse_wolfram_literal(text)

    def test_rejects_malformed_literals(self):
        for text in ('{1,}', '{1', '1/0', '"unfinished', '(* open'):
            with self.subTest(text=text), self.assertRaises(WolframLiteralError):
                parse_wolfram_literal(text)


if __name__ == "__main__":
    unittest.main()
