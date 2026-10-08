"""Read the list/string/integer/rational subset used by LM exports.

No Mathematica evaluation or Python eval is performed.
"""
import re
from fractions import Fraction


class WolframLiteralError(ValueError):
    pass


class _Parser:
    def __init__(self, text):
        # Wolfram source may wrap a string or token with a backslash-newline.
        self.text = re.sub(r"\\\r?\n", "", text.lstrip("\ufeff"))
        self.pos = 0

    def error(self, message):
        line = self.text.count("\n", 0, self.pos) + 1
        raise WolframLiteralError("{} at line {}, offset {}".format(message, line, self.pos))

    def skip(self):
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text.startswith("(*", self.pos):
                depth = 1
                self.pos += 2
                while depth:
                    if self.pos >= len(self.text):
                        self.error("Unterminated comment")
                    if self.text.startswith("(*", self.pos):
                        depth += 1
                        self.pos += 2
                    elif self.text.startswith("*)", self.pos):
                        depth -= 1
                        self.pos += 2
                    else:
                        self.pos += 1
            else:
                break

    def value(self):
        self.skip()
        if self.pos >= len(self.text):
            self.error("Expected a literal")
        char = self.text[self.pos]
        if char == "{":
            return self.list_value()
        if char == '"':
            return self.string_value()
        match = re.match(r"[+-]?\d+", self.text[self.pos:])
        if match:
            numerator = int(match.group())
            self.pos += len(match.group())
            self.skip()
            if self.pos < len(self.text) and self.text[self.pos] == "/":
                self.pos += 1
                self.skip()
                denominator = re.match(r"[+-]?\d+", self.text[self.pos:])
                if not denominator:
                    self.error("Expected an integer denominator")
                self.pos += len(denominator.group())
                if int(denominator.group()) == 0:
                    self.error("Zero denominator")
                return Fraction(numerator, int(denominator.group()))
            return numerator
        self.error("Only lists, strings, integers and rationals are supported")

    def list_value(self):
        self.pos += 1
        result = []
        self.skip()
        if self.pos < len(self.text) and self.text[self.pos] == "}":
            self.pos += 1
            return result
        while True:
            result.append(self.value())
            self.skip()
            if self.pos >= len(self.text):
                self.error("Unterminated list")
            char = self.text[self.pos]
            self.pos += 1
            if char == "}":
                return result
            if char != ",":
                self.error("Expected ',' or '}'")

    def string_value(self):
        self.pos += 1
        chars = []
        escapes = {'"': '"', "\\": "\\", "n": "\n", "r": "\r",
                   "t": "\t", "b": "\b", "f": "\f"}
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == '"':
                return "".join(chars)
            if char == "\\":
                if self.pos >= len(self.text):
                    self.error("Unterminated escape")
                escape = self.text[self.pos]
                self.pos += 1
                if escape not in escapes:
                    self.error("Unsupported string escape: \\" + escape)
                chars.append(escapes[escape])
            else:
                chars.append(char)
        self.error("Unterminated string")


def parse_wolfram_literal(text):
    parser = _Parser(text)
    result = parser.value()
    parser.skip()
    if parser.pos != len(parser.text):
        parser.error("Unexpected trailing content")
    return result
