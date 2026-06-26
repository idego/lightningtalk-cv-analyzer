from cv_validator.gazetteer.resolver import resolve_location


def test_unambiguous_city_country():
    result = resolve_location("Berlin, Germany")
    assert result.is_unambiguous
    assert result.primary.country_code == "DE"


def test_ambiguous_paris():
    result = resolve_location("Paris")
    assert not result.is_unambiguous
    assert len(result.matches) == 2


def test_paris_with_country_hint():
    result = resolve_location("Paris, France")
    assert result.is_unambiguous
    assert result.primary.country_code == "FR"
