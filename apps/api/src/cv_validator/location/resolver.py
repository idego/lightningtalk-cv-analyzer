from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Mapping, Protocol, TypeAlias

from cv_validator.domain import ComponentVersion


class ResolutionLevel(str, Enum):
    COUNTRY = "country"
    REGION = "region"
    LOCALITY = "locality"


class MatchKind(str, Enum):
    CANONICAL = "canonical"
    ALIAS = "alias"


@dataclass(frozen=True)
class LocationMatch:
    record_id: str
    level: ResolutionLevel
    canonical_name: str
    matched_name: str
    match_kind: MatchKind
    country_code: str
    country_name: str
    region_code: str | None = None
    region_name: str | None = None
    population: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "canonical_name",
            "matched_name",
            "country_code",
            "country_name",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.population is not None and self.population < 0:
            raise ValueError("population must not be negative")


@dataclass(frozen=True)
class ScopeResolution:
    level: ResolutionLevel
    canonical_name: str
    country_code: str
    supporting_record_ids: tuple[str, ...]
    region_code: str | None = None
    population: int | None = None

    def __post_init__(self) -> None:
        if not self.canonical_name.strip():
            raise ValueError("canonical_name must not be empty")
        if not self.country_code.strip():
            raise ValueError("country_code must not be empty")
        _require_sorted_unique_nonempty(
            self.supporting_record_ids,
            field_name="supporting_record_ids",
        )
        if self.level is ResolutionLevel.COUNTRY and self.region_code is not None:
            raise ValueError("country resolution cannot have a region_code")
        if self.level is ResolutionLevel.REGION and not self.region_code:
            raise ValueError("region resolution requires region_code")
        if self.population is not None and self.population < 0:
            raise ValueError("population must not be negative")


@dataclass(frozen=True, kw_only=True)
class ResolutionBase:
    input_value: str
    normalized_value: str
    matches: tuple[LocationMatch, ...]
    reference_data_version: ComponentVersion

    def __post_init__(self) -> None:
        if self.normalized_value != normalize_location(self.input_value):
            raise ValueError("normalized_value does not match input_value")
        if not self.reference_data_version.name.strip():
            raise ValueError("reference_data_version.name must not be empty")
        if not self.reference_data_version.version.strip():
            raise ValueError("reference_data_version.version must not be empty")
        record_ids = tuple(match.record_id for match in self.matches)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("matches must contain unique record_id values")
        if self.matches != tuple(sorted(self.matches, key=_match_sort_key)):
            raise ValueError("matches must be stably sorted")


@dataclass(frozen=True, kw_only=True)
class Resolved(ResolutionBase):
    resolution: ScopeResolution
    selected_record_id: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if len(self.matches) != 1:
            raise ValueError("resolved outcome requires exactly one match")
        selected = next(
            (
                match
                for match in self.matches
                if match.record_id == self.selected_record_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("selected_record_id must identify a match")
        if selected.level is not self.resolution.level:
            raise ValueError("selected match must have the resolved level")
        if selected.canonical_name != self.resolution.canonical_name:
            raise ValueError("selected match must have the resolved canonical name")
        if selected.country_code != self.resolution.country_code:
            raise ValueError("selected match must have the resolved country code")
        if selected.region_code != self.resolution.region_code:
            raise ValueError("selected match must have the resolved region code")
        if self.resolution.supporting_record_ids != (self.selected_record_id,):
            raise ValueError("resolved outcome must be supported by the selected record")


@dataclass(frozen=True, kw_only=True)
class Unresolved(ResolutionBase):
    attempted_at: ResolutionLevel

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.matches:
            raise ValueError("unresolved outcome cannot contain matches")


@dataclass(frozen=True, kw_only=True)
class Ambiguous(ResolutionBase):
    ambiguous_at: ResolutionLevel
    common_resolution: ScopeResolution | None

    def __post_init__(self) -> None:
        super().__post_init__()
        if len(self.matches) < 2:
            raise ValueError("ambiguous outcome requires at least two matches")
        if any(match.level is not self.ambiguous_at for match in self.matches):
            raise ValueError("all matches must have the ambiguous level")
        if self.common_resolution is None:
            return
        country_codes = {match.country_code for match in self.matches}
        if "" in country_codes or country_codes != {
            self.common_resolution.country_code
        }:
            raise ValueError(
                "common_resolution requires one non-empty country_code "
                "across all matches"
            )
        if self.common_resolution.level is not ResolutionLevel.COUNTRY:
            raise ValueError("common_resolution must resolve the country level")
        expected_ids = tuple(sorted(match.record_id for match in self.matches))
        if self.common_resolution.supporting_record_ids != expected_ids:
            raise ValueError("common_resolution must be supported by every match")


LocationResolution: TypeAlias = Resolved | Unresolved | Ambiguous


class LocationResolver(Protocol):
    def resolve(
        self,
        value: str,
        *,
        level: ResolutionLevel,
    ) -> LocationResolution: ...


class InMemoryLocationResolver:
    def __init__(
        self,
        *,
        records: Iterable[LocationMatch],
        reference_data_version: ComponentVersion,
        aliases: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        records_by_id: dict[str, LocationMatch] = {}
        canonical_index: dict[tuple[ResolutionLevel, str], set[str]] = {}
        for record in records:
            if record.record_id in records_by_id:
                raise ValueError(f"duplicate record_id: {record.record_id}")
            records_by_id[record.record_id] = record
            canonical_index.setdefault(
                (record.level, normalize_location(record.canonical_name)),
                set(),
            ).add(record.record_id)

        alias_index: dict[tuple[ResolutionLevel, str], dict[str, str]] = {}
        for alias, record_ids in (aliases or {}).items():
            normalized_alias = normalize_location(alias)
            if not normalized_alias:
                raise ValueError("alias must not be empty")
            for record_id in record_ids:
                try:
                    record = records_by_id[record_id]
                except KeyError as exc:
                    raise ValueError(
                        f"alias references unknown record_id: {record_id}"
                    ) from exc
                aliases_by_id = alias_index.setdefault(
                    (record.level, normalized_alias),
                    {},
                )
                previous = aliases_by_id.get(record_id)
                if previous is None or alias < previous:
                    aliases_by_id[record_id] = alias

        if not reference_data_version.name.strip():
            raise ValueError("reference_data_version.name must not be empty")
        if not reference_data_version.version.strip():
            raise ValueError("reference_data_version.version must not be empty")
        self._records_by_id = records_by_id
        self._canonical_index = canonical_index
        self._alias_index = alias_index
        self._reference_data_version = reference_data_version

    def resolve(
        self,
        value: str,
        *,
        level: ResolutionLevel,
    ) -> LocationResolution:
        normalized_value = normalize_location(value)
        if not normalized_value:
            return self._unresolved(value, normalized_value, level)

        canonical_ids = self._canonical_index.get((level, normalized_value), set())
        alias_matches = self._alias_index.get((level, normalized_value), {})
        record_ids = canonical_ids | alias_matches.keys()
        if not record_ids:
            return self._unresolved(value, normalized_value, level)

        matches = tuple(
            sorted(
                (
                    replace(
                        self._records_by_id[record_id],
                        matched_name=(
                            self._records_by_id[record_id].canonical_name
                            if record_id in canonical_ids
                            else alias_matches[record_id]
                        ),
                        match_kind=(
                            MatchKind.CANONICAL
                            if record_id in canonical_ids
                            else MatchKind.ALIAS
                        ),
                    )
                    for record_id in record_ids
                ),
                key=_match_sort_key,
            )
        )
        return _resolution_from_matches(
            input_value=value,
            normalized_value=normalized_value,
            matches=matches,
            reference_data_version=self._reference_data_version,
            level=level,
        )

    def _unresolved(
        self,
        input_value: str,
        normalized_value: str,
        level: ResolutionLevel,
    ) -> Unresolved:
        return Unresolved(
            input_value=input_value,
            normalized_value=normalized_value,
            matches=(),
            reference_data_version=self._reference_data_version,
            attempted_at=level,
        )


def _resolution_from_matches(
    *,
    input_value: str,
    normalized_value: str,
    matches: tuple[LocationMatch, ...],
    reference_data_version: ComponentVersion,
    level: ResolutionLevel,
) -> LocationResolution:
    if not matches:
        return Unresolved(
            input_value=input_value,
            normalized_value=normalized_value,
            matches=(),
            reference_data_version=reference_data_version,
            attempted_at=level,
        )
    if len(matches) == 1:
        match = matches[0]
        resolution = ScopeResolution(
            level=match.level,
            canonical_name=match.canonical_name,
            country_code=match.country_code,
            region_code=match.region_code,
            population=match.population,
            supporting_record_ids=(match.record_id,),
        )
        return Resolved(
            input_value=input_value,
            normalized_value=normalized_value,
            matches=matches,
            reference_data_version=reference_data_version,
            resolution=resolution,
            selected_record_id=match.record_id,
        )

    country_codes = {match.country_code for match in matches}
    common_resolution = None
    if "" not in country_codes and len(country_codes) == 1:
        common_resolution = ScopeResolution(
            level=ResolutionLevel.COUNTRY,
            canonical_name=matches[0].country_name,
            country_code=matches[0].country_code,
            supporting_record_ids=tuple(sorted(match.record_id for match in matches)),
        )
    return Ambiguous(
        input_value=input_value,
        normalized_value=normalized_value,
        matches=matches,
        reference_data_version=reference_data_version,
        ambiguous_at=level,
        common_resolution=common_resolution,
    )


def normalize_location(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _match_sort_key(match: LocationMatch) -> tuple[str, ...]:
    return (
        match.level.value,
        match.country_code,
        match.region_code or "",
        normalize_location(match.canonical_name),
        match.record_id,
        match.match_kind.value,
        normalize_location(match.matched_name),
    )


def _require_sorted_unique_nonempty(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    if any(not value.strip() for value in values):
        raise ValueError(f"{field_name} must not contain empty values")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must contain unique values")
    if values != tuple(sorted(values)):
        raise ValueError(f"{field_name} must be stably sorted")
