"""Competition rules on team composition and track coverage.

``competition.config`` carries the operator-visible rules::

    {"team_size": {"min": 1, "max": 4}, "max_tracks": 2}

Both keys are optional. Leaving one out keeps that rule unlimited, so
competitions configured before these rules existed keep working unchanged.
"""
from __future__ import annotations

MAX_MEMBERS_LIMIT = 200
MAX_TRACKS_LIMIT = 100


def validate_team_rules(config) -> dict:
    """Validate the rule keys of a competition config and return them normalized."""
    if config is None:
        return {}
    if not isinstance(config, dict):
        raise ValueError("赛事配置必须是对象。")
    rules: dict = {}
    if "team_size" in config:
        size = config["team_size"]
        if (not isinstance(size, dict) or set(size) != {"min", "max"}
                or any(isinstance(value, bool) or not isinstance(value, int) for value in size.values())):
            raise ValueError("队伍人数范围需要同时给出最少与最多队员，且都是整数。")
        minimum, maximum = size["min"], size["max"]
        if minimum < 1 or maximum < minimum or maximum > MAX_MEMBERS_LIMIT:
            raise ValueError(f"队伍人数范围需在 1—{MAX_MEMBERS_LIMIT} 之间，且最少不超过最多。")
        rules["team_size"] = {"min": minimum, "max": maximum}
    if "max_tracks" in config:
        value = config["max_tracks"]
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TRACKS_LIMIT:
                raise ValueError(f"最多赛道数需在 1—{MAX_TRACKS_LIMIT} 之间，留空表示不限。")
            rules["max_tracks"] = value
    return rules


def _positive_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def team_size_range(competition) -> tuple[int, int | None]:
    """Minimum and maximum members per team; the maximum is ``None`` when unlimited."""
    config = (competition.config or {}) if competition is not None else {}
    size = config.get("team_size") if isinstance(config, dict) else None
    if not isinstance(size, dict):
        return 1, None
    minimum = _positive_int(size.get("min")) or 1
    maximum = _positive_int(size.get("max"))
    if maximum is not None and maximum < minimum:
        maximum = minimum
    return minimum, maximum


def max_tracks(competition) -> int | None:
    """How many distinct tracks one team may enter; ``None`` when unlimited."""
    config = (competition.config or {}) if competition is not None else {}
    if not isinstance(config, dict):
        return None
    return _positive_int(config.get("max_tracks"))
