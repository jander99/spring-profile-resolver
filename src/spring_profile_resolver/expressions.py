"""Profile expression parsing and evaluation for Spring Boot configurations.

Supports Spring Boot's profile expression syntax:
- Simple profile names: "prod"
- Logical NOT: "!prod"
- Logical AND: "prod & cloud"
- Logical OR: "prod | dev"
- Parentheses for grouping: "(prod & cloud) | dev"

Note: & and | cannot be mixed without parentheses (Spring Boot restriction).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator

from .exceptions import ProfileExpressionError


class TokenType(Enum):
    """Token types for profile expression lexer."""

    PROFILE = auto()  # Profile name
    NOT = auto()  # !
    AND = auto()  # &
    OR = auto()  # |
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    EOF = auto()  # End of expression


@dataclass
class Token:
    """A single token from the expression lexer."""

    type: TokenType
    value: str
    position: int


class ProfileExpr(ABC):
    """Abstract base class for profile expression AST nodes."""

    @abstractmethod
    def evaluate(self, active_profiles: set[str]) -> bool:
        """Evaluate the expression against active profiles."""
        pass

    @abstractmethod
    def __str__(self) -> str:
        """Return string representation of the expression."""
        pass


@dataclass
class ProfileName(ProfileExpr):
    """A simple profile name."""

    name: str

    def evaluate(self, active_profiles: set[str]) -> bool:
        return self.name in active_profiles

    def __str__(self) -> str:
        return self.name


@dataclass
class NotExpr(ProfileExpr):
    """Logical NOT expression."""

    operand: ProfileExpr

    def evaluate(self, active_profiles: set[str]) -> bool:
        return not self.operand.evaluate(active_profiles)

    def __str__(self) -> str:
        return f"!{self.operand}"


@dataclass
class AndExpr(ProfileExpr):
    """Logical AND expression."""

    left: ProfileExpr
    right: ProfileExpr

    def evaluate(self, active_profiles: set[str]) -> bool:
        return self.left.evaluate(active_profiles) and self.right.evaluate(
            active_profiles
        )

    def __str__(self) -> str:
        return f"({self.left} & {self.right})"


@dataclass
class OrExpr(ProfileExpr):
    """Logical OR expression."""

    left: ProfileExpr
    right: ProfileExpr

    def evaluate(self, active_profiles: set[str]) -> bool:
        return self.left.evaluate(active_profiles) or self.right.evaluate(
            active_profiles
        )

    def __str__(self) -> str:
        return f"({self.left} | {self.right})"


class Lexer:
    """Tokenizer for profile expressions."""

    def __init__(self, expression: str):
        self.expression = expression
        self.pos = 0
        self.length = len(expression)

    def _skip_whitespace(self) -> None:
        while self.pos < self.length and self.expression[self.pos].isspace():
            self.pos += 1

    def _read_profile_name(self) -> str:
        """Read a profile name (alphanumeric, -, _, ., +, @)."""
        start = self.pos
        while self.pos < self.length:
            char = self.expression[self.pos]
            # Spring allows letters, numbers, and these characters in profile names
            if char.isalnum() or char in "-_.+@":
                self.pos += 1
            else:
                break
        return self.expression[start : self.pos]

    def tokens(self) -> Iterator[Token]:
        """Generate tokens from the expression."""
        while self.pos < self.length:
            self._skip_whitespace()
            if self.pos >= self.length:
                break

            char = self.expression[self.pos]
            start_pos = self.pos

            if char == "!":
                self.pos += 1
                yield Token(TokenType.NOT, "!", start_pos)
            elif char == "&":
                self.pos += 1
                yield Token(TokenType.AND, "&", start_pos)
            elif char == "|":
                self.pos += 1
                yield Token(TokenType.OR, "|", start_pos)
            elif char == "(":
                self.pos += 1
                yield Token(TokenType.LPAREN, "(", start_pos)
            elif char == ")":
                self.pos += 1
                yield Token(TokenType.RPAREN, ")", start_pos)
            elif char.isalnum() or char in "-_.+@":
                name = self._read_profile_name()
                if name:
                    yield Token(TokenType.PROFILE, name, start_pos)
                else:
                    raise ProfileExpressionError(
                        f"Invalid character at position {start_pos}: '{char}'"
                    )
            else:
                raise ProfileExpressionError(
                    f"Unexpected character at position {start_pos}: '{char}'"
                )

        yield Token(TokenType.EOF, "", self.pos)


class Parser:
    """Recursive descent parser for profile expressions.

    Grammar:
        expression := or_expr
        or_expr    := and_expr ("|" and_expr)*
        and_expr   := unary ("&" unary)*
        unary      := "!" unary | primary
        primary    := PROFILE | "(" expression ")"

    Note: Spring Boot doesn't allow mixing & and | without parentheses,
    so we enforce that during parsing.
    """

    def __init__(self, expression: str):
        self.expression = expression
        self.lexer = Lexer(expression)
        self.tokens = list(self.lexer.tokens())
        self.pos = 0
        self.current = self.tokens[0] if self.tokens else Token(TokenType.EOF, "", 0)

    def _advance(self) -> Token:
        """Advance to the next token."""
        token = self.current
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current = self.tokens[self.pos]
        return token

    def _expect(self, token_type: TokenType) -> Token:
        """Expect a specific token type, raising error if not found."""
        if self.current.type != token_type:
            raise ProfileExpressionError(
                f"Expected {token_type.name} at position {self.current.position}, "
                f"got {self.current.type.name}"
            )
        return self._advance()

    def parse(self) -> ProfileExpr:
        """Parse the expression and return the AST root."""
        if self.current.type == TokenType.EOF:
            raise ProfileExpressionError("Empty profile expression")

        expr = self._parse_or_expr()

        if self.current.type != TokenType.EOF:
            raise ProfileExpressionError(
                f"Unexpected token at position {self.current.position}: "
                f"'{self.current.value}'"
            )

        return expr

    def _parse_or_expr(self) -> ProfileExpr:
        """Parse OR expression: and_expr ("|" and_expr)*"""
        left = self._parse_and_expr()

        while self.current.type == TokenType.OR:
            self._advance()
            right = self._parse_and_expr()
            left = OrExpr(left, right)

        return left

    def _parse_and_expr(self) -> ProfileExpr:
        """Parse AND expression: unary ("&" unary)*"""
        left = self._parse_unary()

        while self.current.type == TokenType.AND:
            self._advance()
            right = self._parse_unary()
            left = AndExpr(left, right)

        return left

    def _parse_unary(self) -> ProfileExpr:
        """Parse unary expression: "!" unary | primary"""
        if self.current.type == TokenType.NOT:
            self._advance()
            operand = self._parse_unary()
            return NotExpr(operand)

        return self._parse_primary()

    def _parse_primary(self) -> ProfileExpr:
        """Parse primary expression: PROFILE | "(" expression ")" """
        if self.current.type == TokenType.PROFILE:
            token = self._advance()
            return ProfileName(token.value)

        if self.current.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_or_expr()
            self._expect(TokenType.RPAREN)
            return expr

        raise ProfileExpressionError(
            f"Expected profile name or '(' at position {self.current.position}, "
            f"got '{self.current.value}'"
        )


def parse_profile_expression(expression: str) -> ProfileExpr:
    """Parse a profile expression string into an AST.

    Args:
        expression: Profile expression like "prod & cloud" or "(dev | test) & !staging"

    Returns:
        ProfileExpr AST node

    Raises:
        ProfileExpressionError: If the expression is invalid
    """
    parser = Parser(expression.strip())
    return parser.parse()


def evaluate_profile_expression(expression: str, active_profiles: list[str]) -> bool:
    """Evaluate a profile expression against active profiles.

    Args:
        expression: Profile expression string
        active_profiles: List of currently active profile names

    Returns:
        True if the expression matches the active profiles

    Raises:
        ProfileExpressionError: If the expression is invalid
    """
    expr = parse_profile_expression(expression)
    return expr.evaluate(set(active_profiles))


def is_simple_profile(expression: str) -> bool:
    """Check if an expression is a simple profile name (no operators).

    Args:
        expression: Profile expression string

    Returns:
        True if it's just a simple profile name with no operators
    """
    expression = expression.strip()
    if not expression:
        return False

    # Check for any operator characters
    for char in expression:
        if char in "!&|()":
            return False

    return True
