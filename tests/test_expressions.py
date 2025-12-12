"""Tests for profile expression parsing and evaluation."""

import pytest

from spring_profile_resolver.exceptions import ProfileExpressionError
from spring_profile_resolver.expressions import (
    AndExpr,
    Lexer,
    NotExpr,
    OrExpr,
    Parser,
    ProfileName,
    Token,
    TokenType,
    evaluate_profile_expression,
    is_simple_profile,
    parse_profile_expression,
)


class TestLexer:
    """Tests for the expression lexer."""

    def test_simple_profile(self):
        tokens = list(Lexer("prod").tokens())
        assert len(tokens) == 2
        assert tokens[0] == Token(TokenType.PROFILE, "prod", 0)
        assert tokens[1].type == TokenType.EOF

    def test_profile_with_special_chars(self):
        tokens = list(Lexer("my-profile_name.v2+test@local").tokens())
        assert tokens[0].type == TokenType.PROFILE
        assert tokens[0].value == "my-profile_name.v2+test@local"

    def test_not_operator(self):
        tokens = list(Lexer("!prod").tokens())
        assert tokens[0] == Token(TokenType.NOT, "!", 0)
        assert tokens[1] == Token(TokenType.PROFILE, "prod", 1)

    def test_and_operator(self):
        tokens = list(Lexer("prod & cloud").tokens())
        assert tokens[0] == Token(TokenType.PROFILE, "prod", 0)
        assert tokens[1] == Token(TokenType.AND, "&", 5)
        assert tokens[2] == Token(TokenType.PROFILE, "cloud", 7)

    def test_or_operator(self):
        tokens = list(Lexer("dev | test").tokens())
        assert tokens[0] == Token(TokenType.PROFILE, "dev", 0)
        assert tokens[1] == Token(TokenType.OR, "|", 4)
        assert tokens[2] == Token(TokenType.PROFILE, "test", 6)

    def test_parentheses(self):
        tokens = list(Lexer("(prod)").tokens())
        assert tokens[0] == Token(TokenType.LPAREN, "(", 0)
        assert tokens[1] == Token(TokenType.PROFILE, "prod", 1)
        assert tokens[2] == Token(TokenType.RPAREN, ")", 5)

    def test_complex_expression(self):
        tokens = list(Lexer("(prod & cloud) | !dev").tokens())
        types = [t.type for t in tokens]
        assert types == [
            TokenType.LPAREN,
            TokenType.PROFILE,
            TokenType.AND,
            TokenType.PROFILE,
            TokenType.RPAREN,
            TokenType.OR,
            TokenType.NOT,
            TokenType.PROFILE,
            TokenType.EOF,
        ]

    def test_whitespace_handling(self):
        tokens = list(Lexer("  prod   &   cloud  ").tokens())
        assert tokens[0].value == "prod"
        assert tokens[1].type == TokenType.AND
        assert tokens[2].value == "cloud"

    def test_invalid_character(self):
        with pytest.raises(ProfileExpressionError, match="Unexpected character"):
            list(Lexer("prod # comment").tokens())


class TestParser:
    """Tests for the expression parser."""

    def test_simple_profile(self):
        expr = parse_profile_expression("prod")
        assert isinstance(expr, ProfileName)
        assert expr.name == "prod"

    def test_not_expression(self):
        expr = parse_profile_expression("!prod")
        assert isinstance(expr, NotExpr)
        assert isinstance(expr.operand, ProfileName)
        assert expr.operand.name == "prod"

    def test_double_not(self):
        expr = parse_profile_expression("!!prod")
        assert isinstance(expr, NotExpr)
        assert isinstance(expr.operand, NotExpr)
        assert expr.operand.operand.name == "prod"

    def test_and_expression(self):
        expr = parse_profile_expression("prod & cloud")
        assert isinstance(expr, AndExpr)
        assert expr.left.name == "prod"
        assert expr.right.name == "cloud"

    def test_or_expression(self):
        expr = parse_profile_expression("dev | test")
        assert isinstance(expr, OrExpr)
        assert expr.left.name == "dev"
        assert expr.right.name == "test"

    def test_parentheses(self):
        expr = parse_profile_expression("(prod)")
        assert isinstance(expr, ProfileName)
        assert expr.name == "prod"

    def test_and_chain(self):
        expr = parse_profile_expression("a & b & c")
        # Should parse as ((a & b) & c)
        assert isinstance(expr, AndExpr)
        assert isinstance(expr.left, AndExpr)
        assert expr.left.left.name == "a"
        assert expr.left.right.name == "b"
        assert expr.right.name == "c"

    def test_or_chain(self):
        expr = parse_profile_expression("a | b | c")
        # Should parse as ((a | b) | c)
        assert isinstance(expr, OrExpr)
        assert isinstance(expr.left, OrExpr)

    def test_mixed_with_parentheses(self):
        expr = parse_profile_expression("(a & b) | c")
        assert isinstance(expr, OrExpr)
        assert isinstance(expr.left, AndExpr)
        assert expr.right.name == "c"

    def test_complex_nested(self):
        expr = parse_profile_expression("(a | b) & (c | d)")
        assert isinstance(expr, AndExpr)
        assert isinstance(expr.left, OrExpr)
        assert isinstance(expr.right, OrExpr)

    def test_not_with_parentheses(self):
        expr = parse_profile_expression("!(a & b)")
        assert isinstance(expr, NotExpr)
        assert isinstance(expr.operand, AndExpr)

    def test_empty_expression(self):
        with pytest.raises(ProfileExpressionError, match="Empty"):
            parse_profile_expression("")

    def test_empty_whitespace(self):
        with pytest.raises(ProfileExpressionError, match="Empty"):
            parse_profile_expression("   ")

    def test_unclosed_paren(self):
        with pytest.raises(ProfileExpressionError, match="Expected RPAREN"):
            parse_profile_expression("(prod")

    def test_unexpected_token(self):
        with pytest.raises(ProfileExpressionError, match="Unexpected token"):
            parse_profile_expression("prod cloud")

    def test_missing_operand(self):
        with pytest.raises(ProfileExpressionError, match="Expected profile"):
            parse_profile_expression("prod &")


class TestEvaluation:
    """Tests for expression evaluation."""

    def test_simple_match(self):
        assert evaluate_profile_expression("prod", ["prod"]) is True
        assert evaluate_profile_expression("prod", ["dev"]) is False
        assert evaluate_profile_expression("prod", ["prod", "dev"]) is True

    def test_not_expression(self):
        assert evaluate_profile_expression("!prod", ["dev"]) is True
        assert evaluate_profile_expression("!prod", ["prod"]) is False
        assert evaluate_profile_expression("!prod", []) is True

    def test_and_expression(self):
        assert evaluate_profile_expression("prod & cloud", ["prod", "cloud"]) is True
        assert evaluate_profile_expression("prod & cloud", ["prod"]) is False
        assert evaluate_profile_expression("prod & cloud", ["cloud"]) is False
        assert evaluate_profile_expression("prod & cloud", []) is False

    def test_or_expression(self):
        assert evaluate_profile_expression("prod | dev", ["prod"]) is True
        assert evaluate_profile_expression("prod | dev", ["dev"]) is True
        assert evaluate_profile_expression("prod | dev", ["prod", "dev"]) is True
        assert evaluate_profile_expression("prod | dev", ["staging"]) is False

    def test_complex_expression(self):
        # (prod & cloud) | dev
        expr = "(prod & cloud) | dev"
        assert evaluate_profile_expression(expr, ["prod", "cloud"]) is True
        assert evaluate_profile_expression(expr, ["dev"]) is True
        assert evaluate_profile_expression(expr, ["prod"]) is False
        assert evaluate_profile_expression(expr, ["staging"]) is False

    def test_not_with_and(self):
        # prod & !staging
        expr = "prod & !staging"
        assert evaluate_profile_expression(expr, ["prod"]) is True
        assert evaluate_profile_expression(expr, ["prod", "staging"]) is False
        assert evaluate_profile_expression(expr, ["staging"]) is False

    def test_not_with_or(self):
        # !prod | dev
        expr = "!prod | dev"
        assert evaluate_profile_expression(expr, []) is True
        assert evaluate_profile_expression(expr, ["dev"]) is True
        assert evaluate_profile_expression(expr, ["prod"]) is False
        assert evaluate_profile_expression(expr, ["prod", "dev"]) is True

    def test_negated_group(self):
        # !(prod & cloud)
        expr = "!(prod & cloud)"
        assert evaluate_profile_expression(expr, ["prod", "cloud"]) is False
        assert evaluate_profile_expression(expr, ["prod"]) is True
        assert evaluate_profile_expression(expr, []) is True

    def test_real_world_example(self):
        # (production & cloud) | (staging & !local)
        expr = "(production & cloud) | (staging & !local)"
        assert evaluate_profile_expression(expr, ["production", "cloud"]) is True
        assert evaluate_profile_expression(expr, ["staging"]) is True
        assert evaluate_profile_expression(expr, ["staging", "local"]) is False
        assert evaluate_profile_expression(expr, ["production"]) is False


class TestIsSimpleProfile:
    """Tests for the is_simple_profile helper."""

    def test_simple_names(self):
        assert is_simple_profile("prod") is True
        assert is_simple_profile("dev") is True
        assert is_simple_profile("my-profile") is True
        assert is_simple_profile("profile_v2") is True

    def test_expressions(self):
        assert is_simple_profile("!prod") is False
        assert is_simple_profile("prod & cloud") is False
        assert is_simple_profile("prod | dev") is False
        assert is_simple_profile("(prod)") is False

    def test_empty(self):
        assert is_simple_profile("") is False
        assert is_simple_profile("   ") is False


class TestStringRepresentation:
    """Tests for expression string representation."""

    def test_simple_profile_str(self):
        expr = parse_profile_expression("prod")
        assert str(expr) == "prod"

    def test_not_str(self):
        expr = parse_profile_expression("!prod")
        assert str(expr) == "!prod"

    def test_and_str(self):
        expr = parse_profile_expression("prod & cloud")
        assert str(expr) == "(prod & cloud)"

    def test_or_str(self):
        expr = parse_profile_expression("prod | dev")
        assert str(expr) == "(prod | dev)"
