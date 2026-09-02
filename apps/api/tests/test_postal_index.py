from pathlib import Path

from cv_validator.location import SQLitePostalCodeResolver, build_postal_index


FIXTURE = Path(__file__).parent / "fixtures" / "postal" / "allCountries.txt"


def test_builds_versioned_offline_postal_index_and_resolves_city(tmp_path):
    index = tmp_path / "postal-codes.sqlite3"
    manifest = tmp_path / "postal-codes.manifest.json"

    metadata = build_postal_index(
        source_path=FIXTURE,
        source_url="https://example.test/postal/allCountries.zip",
        snapshot_date="2026-09-02",
        output_index=index,
        output_manifest=manifest,
    )
    resolver = SQLitePostalCodeResolver(index, manifest)

    assert metadata["source"]["dataset"] == "GeoNames postal codes"
    assert resolver.validate("00-001", city="Warsaw", country_code="PL").status == "resolved"
    assert resolver.validate("00-001", city="Krakow", country_code="PL").status == "mismatch"
    assert resolver.validate("99-999", city="Warsaw", country_code="PL").status == "unresolved"
    resolver.close()
