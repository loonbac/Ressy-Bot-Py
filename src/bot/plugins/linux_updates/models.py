from __future__ import annotations

from typing import NotRequired, TypedDict


class ProductInfo(TypedDict):
    slug: str
    display_name: str
    last_check_at: int | None
    last_check_status: str  # 'ok' | 'error'
    last_check_error: str | None
    release_count: int
    active_count: int
    stale: bool
    updated_at: str  # humanizado, ej. "hace 2 horas"


class ReleaseInfo(TypedDict):
    cycle: str
    codename: str | None
    release_date: str | None
    eol_date: str | None
    latest_version: str | None
    latest_release_date: str | None
    lts: bool | None
    support_date: str | None
    extended_support_date: str | None
    release_label: str | None
    days_until_eol: int | None
    status: str  # 'active' | 'expired' | 'unknown'


class ProductDetail(TypedDict):
    slug: str
    display_name: str
    last_check_at: int | None
    last_check_status: str
    last_check_error: str | None
    releases: list[ReleaseInfo]


class SummaryInfo(TypedDict):
    total_releases: int
    active_releases: int
    expiring_soon: list[dict]  # [{slug, cycle, eol_date, days_left}]
    expired: list[dict]
    no_eol_date: list[dict]  # [{slug, cycle, note}]


class ConfigInfo(TypedDict):
    enabled: str
    refresh_interval_hours: str
    eol_warning_days: str
    discord_channel_id: str
