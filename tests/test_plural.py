import pytest

from ai_researcher.digest import plural

FORMS = ("публикация", "публикации", "публикаций")


@pytest.mark.parametrize(
    "count,expected",
    [
        (1, "публикация"),
        (2, "публикации"),
        (4, "публикации"),
        (5, "публикаций"),
        (11, "публикаций"),
        (12, "публикаций"),
        (21, "публикация"),
        (22, "публикации"),
        (25, "публикаций"),
        (101, "публикация"),
        (111, "публикаций"),
        (0, "публикаций"),
    ],
)
def test_russian_plural_agreement(count, expected):
    assert plural(count, *FORMS) == expected
