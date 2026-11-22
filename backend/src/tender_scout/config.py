from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The shortest pause between two requests to the source that can be configured.
# ADR 0001: the source is someone else's server, and a setting must not be able
# to turn this project into a load on it.
SHORTEST_PAUSE = 1.0


class Settings(BaseSettings):
    """Runtime configuration, read from ``TS_*`` environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="TS_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: str = "postgresql+asyncpg://scout:scout@localhost:5433/tender_scout"

    source_url: str = "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl"
    # Says who is asking. Put a way to reach you here when you run this for real.
    user_agent: str = "tender-scout/0.1"
    # Training services, the first niche: "Usługi szkoleniowe" and the whole of
    # "Usługi edukacyjne i szkoleniowe".
    cpv_codes: list[str] = ["80500000-9", "80000000-4"]
    # Seconds between two requests to the source.
    source_pause: float = Field(default=2.0, ge=SHORTEST_PAUSE)
    # The most requests one run may make. A run that reaches it stops, and the
    # next run carries on from what is already kept.
    source_requests_per_run: int = Field(default=300, ge=1)
    # A kept notice that still takes offers is read again after this many days,
    # because a search result does not say when a notice was edited.
    refresh_after_days: int = Field(default=7, ge=1)
