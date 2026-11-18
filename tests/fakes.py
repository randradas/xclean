"""Test doubles shared by several test files."""

from xclean.tokens import TokenSet


class MemoryTokenStore:
    """A token store kept in memory. Satisfies `xclean.tokens.TokenStore`."""

    def __init__(self, tokens: TokenSet | None = None) -> None:
        self._tokens = tokens

    def load(self) -> TokenSet | None:
        return self._tokens

    def save(self, tokens: TokenSet) -> None:
        self._tokens = tokens

    def clear(self) -> None:
        self._tokens = None
