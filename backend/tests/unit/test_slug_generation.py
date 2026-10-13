import pytest

from app.utils.text.slug_generator import generate_slug


def test_basic_slug() -> None:
    slug_result = generate_slug("My Project")
    assert slug_result == "my-project"


def test_accented_characters() -> None:
    slug_result = generate_slug("Café Médiatech")
    assert slug_result == "cafe-mediatech"


def test_special_characters() -> None:
    slug_result = generate_slug("hello@world!#")
    assert slug_result == "helloworld"


def test_multiple_spaces_and_hyphens() -> None:
    slug_result = generate_slug("a - - b")
    assert slug_result == "a-b"


def test_underscores_replacement() -> None:
    slug_result = generate_slug("my_project")
    assert slug_result == "my-project"


def test_leading_trailing_hyphens() -> None:
    slug_result = generate_slug(" -hello- ")
    assert slug_result == "hello"


def test_empty_string() -> None:
    with pytest.raises(ValueError):
        generate_slug("")


def test_whitespace_only_raises() -> None:
    with pytest.raises(ValueError):
        generate_slug("    ")


def test_symbols_only_raises() -> None:
    with pytest.raises(ValueError):
        generate_slug("@#$%!")


def test_unicode_only() -> None:
    slug_result = generate_slug("日本語")
    assert slug_result == "ribenyu"
