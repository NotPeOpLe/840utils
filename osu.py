from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from enum import Enum, IntEnum
from typing import List, Optional, TypeVar, Union

from httpx import AsyncClient, HTTPStatusError
from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from config import config

T = TypeVar('T')


BASE_URL = "https://osu.ppy.sh"
API_URL = BASE_URL + "/api/v2"
OAUTH_URL = BASE_URL + "/oauth"
_client_credentials: AccessToken = None


class AccessToken(BaseModel):
    token_type: str
    expires_in: int
    access_token: str
    refresh_token: Optional[str] = None


async def get_token(*, code: str = None, client_credentials: bool = False) -> AccessToken:
    body = {
        "client_id": config.osu_client_id,
        "client_secret": config.osu_client_secret
    }

    if client_credentials:
        body["grant_type"] = "client_credentials"
        body["scope"] = "public"
    elif code:
        body["grant_type"] = "authorization_code"
        body["code"] = code
        body["redirect_uri"] = config.osu_client_redirect_uri
    else:
        raise TypeError()

    async with AsyncClient() as client:
        resp = await client.post(OAUTH_URL+"/token", json=body)
        resp.raise_for_status()

    return AccessToken(**resp.json())


async def get_client_credentials():
    global _client_credentials
    _client_credentials = await get_token(client_credentials=True)


def api_client():
    return AsyncClient(
        base_url=API_URL,
        headers={
            "Authorization": "Bearer " + _client_credentials.access_token
        }
    )


async def from_api(method: str, uri: str, return_class: T, **kwargs) -> Union[T, None]:
    async with api_client() as client:
        resp = await client.request(method, uri, **kwargs)
    if resp.status_code == 404:
        return None
    elif resp.status_code > 400:
        resp.raise_for_status()
    return return_class(**resp.json())


class GameModeInt(IntEnum):
    osu = 0
    taiko = 1
    fruits = 2
    mania = 3


class GameMode(str, Enum):
    osu = 'osu'
    taiko = 'taiko'
    fruits = 'fruits'
    mania = 'mania'


class RankStatus(IntEnum):
    graveyard = -2
    wip = -1
    pending = 0
    ranked = 1
    approved = 2
    qualified = 3
    loved = 4


class RankStatusStr(str, Enum):
    graveyard = 'graveyard'
    wip = 'wip'
    pending = 'pending'
    ranked = 'ranked'
    approved = 'approved'
    qualified = 'qualified'
    loved = 'loved'


class Availability(SQLModel):
    download_disabled: bool
    more_information: Optional[str] = None


class Hype(SQLModel):
    current: int
    required: int


class Nominations(Hype):
    pass


class Covers(SQLModel):
    cover: str
    cover_2x: Optional[str] = Field(None, alias="cover@2x")
    card: str
    card_2x: Optional[str] = Field(None, alias="card@2x")
    list: str
    list_2x: Optional[str] = Field(None, alias="list@2x")
    slimcover: str
    slimcover_2x: Optional[str] = Field(None, alias="slimcover@2x")


class BeatmapsetCompact(SQLModel):
    artist: str
    artist_unicode: str
    covers:	Covers
    creator: str
    favourite_count: int
    id: int
    nsfw: bool
    play_count: int
    preview_url: str
    source: str
    status: str
    title: str
    title_unicode: str
    track_id: Optional[int] = None
    user_id: int
    video: bool
    # beatmaps: List[Beatmap] = []
    # converts: Optional[str] = None
    # current_user_attributes: Optional[str] = None
    # description: Optional[str] = None
    # discussions: Optional[str] = None
    # events: Optional[str] = None
    # genre: Optional[str] = None
    # has_favourited: Optional[bool] = None
    # language: Optional[str] = None
    # nominations: Optional[str] = None
    # ratings: List[int] = []
    # recent_favourites: Optional[str] = None
    # related_users: Optional[str] = None
    # user: Optional[str] = None


class Beatmapset(BeatmapsetCompact):
    availability: Availability
    bpm: float
    can_be_hyped: bool
    creator: str
    discussion_enabled: bool
    discussion_locked: bool
    hype: Optional[Hype] = None
    is_scoreable: bool
    last_updated: datetime
    legacy_thread_url: Optional[str] = None
    nominations: Optional[Nominations] = None
    ranked: RankStatus
    ranked_date: Optional[datetime] = None
    source: str
    storyboard: bool
    submitted_date: Optional[datetime] = None
    tags: str

    ratings: List[int] = []


class Failtimes(SQLModel):
    exit: List[int] = []
    fail: List[int] = []


class BeatmapCompact(SQLModel):
    beatmapset_id: int
    difficulty_rating: float
    id: int
    mode: GameMode
    status: RankStatusStr
    total_length: int
    user_id: int
    version: str

    beatmapset: Union[Beatmapset, None] = None
    checksum: Optional[str] = None
    failtimes: Optional[Failtimes] = None
    max_combo: Optional[int] = None


class Beatmap(BeatmapCompact):
    accuracy: float
    ar: float
    beatmapset_id: int
    bpm: Optional[float] = None
    convert: bool
    count_circles: int
    count_sliders: int
    count_spinners: int
    cs: float
    deleted_at: Optional[datetime] = None
    drain: float
    hit_length: int
    is_scoreable: bool
    last_updated: Optional[datetime] = None
    mode_int: int
    passcount: int
    playcount: int
    ranked: RankStatus
    url: str


class Beatmaps(SQLModel):
    beatmaps: List[BeatmapCompact] = []


class DifficultyAttributesBase(SQLModel):
    max_combo: int
    star_rating: float


class OsuDifficultyAttributes(DifficultyAttributesBase):
    aim_difficulty: float
    approach_rate: float
    flashlight_difficulty: float
    overall_difficulty: float
    slider_factor: float
    speed_difficulty: float


class TaikoDifficultyAttributes(DifficultyAttributesBase):
    approach_rate: float
    stamina_difficulty: float
    rhythm_difficulty: float
    colour_difficulty: float
    great_hit_window: float


class FruitsDifficultyAttributes(DifficultyAttributesBase):
    approach_rate: float


class ManiaDifficultyAttributes(DifficultyAttributesBase):
    great_hit_window: float
    score_multiplier: float


class DifficultyAttributes(SQLModel):
    attributes: Union[
        OsuDifficultyAttributes,
        TaikoDifficultyAttributes,
        ManiaDifficultyAttributes,
        FruitsDifficultyAttributes,
    ]


class BeatmapPlaycount(SQLModel):
    beatmap_id: int
    beatmap: Optional[BeatmapCompact] = None
    beatmapset: Optional[BeatmapsetCompact] = None
    count: int


class Kudosu(SQLModel):
    available: int
    total: int


class UserAccountHistory(SQLModel):
    description: Optional[str] = None
    id: int
    length: int
    timestamp: datetime
    type: str


class ProfileBanner(SQLModel):
    id: int
    tournament_id: int
    image: str


class UserBadge(SQLModel):
    awarded_at: datetime
    description: str
    image_url: str
    url: str


class UserGroup(SQLModel):
    playmodes: List[str] = []


class UserSilence(SQLModel):
    id: int
    user_id: int


class GradeCounts(SQLModel):
    a: int
    s: int
    sh: int
    ss: int
    ssh: int


class Level(SQLModel):
    current: int
    progress: int


class UserStatistics(SQLModel):
    grade_counts: GradeCounts
    hit_accuracy: int
    is_ranked: bool
    level: Level
    maximum_combo: int
    play_count: int
    play_time: int
    pp: int
    global_rank: Optional[int] = None
    ranked_score: int
    replays_watched_by_others: int
    total_hits: int
    total_score: int
    user: Optional[UserCompact] = None


class Country(SQLModel):
    code: str
    name: str


class UserCover(SQLModel):
    custom_url: Optional[str] = None
    url: Optional[str] = None
    id: Optional[int] = None


class MonthlyCount(SQLModel):
    start_date: date
    count: int


class Page(SQLModel):
    html: str
    raw: str


class UserAchievements(SQLModel):
    achieved_at: datetime
    achievement_id: int


class RankHistory(SQLModel):
    mode: GameMode
    data: List[int] = []


class UserCompact(SQLModel):
    avatar_url: str
    country_code: str
    default_group: str
    id: int
    is_active: bool
    is_bot: bool
    is_deleted: bool
    is_online: bool
    is_supporter: bool
    last_visit: Optional[datetime] = None
    pm_friends_only: bool
    profile_colour: Optional[str] = None
    username: str


class User(UserCompact):
    cover_url: str
    discord: Optional[str] = None
    has_supported: bool
    interests: Optional[str] = None
    join_date: datetime
    kudosu: Kudosu
    location: Optional[str] = None
    max_blocks: int
    max_friends: int
    occupation: Optional[str] = None
    playmode: GameMode
    playstyle: List[str] = []
    post_count: int
    profile_order: List[str] = []
    title: Optional[str] = None
    title_url: Optional[str] = None
    twitter: Optional[str] = None
    website: Optional[str] = None

    account_history: List[UserAccountHistory] = []
    active_tournament_banner: Optional[ProfileBanner] = None
    badges: List[UserBadge] = []
    beatmap_playcounts_count: Optional[int] = None
    country: Optional[Country] = None
    cover: UserCover
    favourite_beatmapset_count: Optional[int] = None
    follower_count: Optional[int] = None
    graveyard_beatmapset_count: Optional[int] = None
    groups: List[UserGroup] = []
    is_restricted: Optional[bool] = None
    loved_beatmapset_count: Optional[int] = None
    monthly_playcounts: List[MonthlyCount] = []
    page: Optional[Page] = None
    pending_beatmapset_count: Optional[int] = None
    previous_usernames: List[str] = []
    rank_history: RankHistory
    ranked_beatmapset_count: Optional[int] = None
    replays_watched_counts: List[MonthlyCount] = []
    scores_best_count: Optional[int] = None
    scores_first_count: Optional[int] = None
    scores_recent_count: Optional[int] = None
    statistics: Optional[UserStatistics] = None
    support_level: Optional[int] = None
    user_achievements: List[UserAchievements] = []


class ScoreStatistics(SQLModel):
    count_50: int
    count_100: int
    count_300: int
    count_geki: int
    count_katu: int
    count_miss: int


class Score(SQLModel):
    id: int
    best_id: Optional[int] = None
    user_id: int
    accuracy: float
    mods: List[str] = []
    score: int
    max_combo: int
    perfect: bool
    statistics: ScoreStatistics
    passed: bool
    pp: Optional[float] = None
    rank: str
    created_at: datetime
    mode: GameMode
    mode_int: GameModeInt
    replay: bool


class Match(SQLModel):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    name: str


class LegacyMatchEventDetail(SQLModel):
    type: str
    text: Optional[str] = None


class LegacyMatchScoreSlot(SQLModel):
    slot: int
    team: str
    passed: bool = Field(alias="pass")


class LegacyMatchScore(Score):
    match: LegacyMatchScoreSlot
    # current_user_attributes


class LegacyMatchGame(SQLModel):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    mode: GameMode
    mode_int: GameModeInt
    scoring_type: str
    team_type: str
    mods: List[str] = []
    beatmap: Beatmap
    scores: List[Score] = []


class LegacyMatchEvent(SQLModel):
    id: int
    detail: LegacyMatchEventDetail
    timestamp: datetime
    user_id: Optional[int] = None
    game: Optional[LegacyMatchGame] = None


class LegacyMatchUser(UserCompact):
    country: Country


class LegacyMatch(SQLModel):
    match: Match
    events: List[LegacyMatchEvent] = []
    users: List[LegacyMatchUser] = []
    first_event_id: int
    latest_event_id: int
    current_game_id: Optional[int] = None


UserStatistics.update_forward_refs()


async def get_beatmap(beatmap: int):
    return await from_api('GET', f'/beatmaps/{beatmap}', Beatmap)


async def get_beatmaps(ids: List[Union[str, int]]):
    return await from_api('GET', f'/beatmaps', Beatmaps, params={"ids[]": ids})


async def get_beatmap_attributes(
    beatmap: Union[int, BeatmapCompact, Beatmap],
    mods: Union[int, List[str]] = None,
    ruleset: GameMode = None,
    ruleset_id: GameModeInt = None
):
    headers = {
        "Content-Type": "application/json"
    }
    body = {}
    beatmap_id = (beatmap, beatmap.id)[
        isinstance(beatmap, (BeatmapCompact, Beatmap))]
    if mods is not None:
        body["mods"] = mods
    if ruleset is not None:
        body["ruleset"] = ruleset
    if ruleset_id is not None:
        body["ruleset_id"] = ruleset_id
    return await from_api('POST', f'/beatmaps/{beatmap_id}/attributes', DifficultyAttributes, headers=headers, data=json.dumps(body))


async def get_user(user: Union[str, int], *, mode: Optional[GameMode] = "", key: str = None):
    params = {}
    if key is not None:
        params["key"] = key
    return await from_api('GET', f'/users/{user}/{mode}', User, params=key)


async def test():
    from rich import print

    await get_client_credentials()
    # beatmap = await get_beatmap(351189)
    # print(beatmap)
    # beatmaps = await get_beatmaps([351189, 646713, 2665294, 1494828])
    # print(beatmaps)
    # user_osu = await get_user("840", mode=GameMode.osu)
    # print(user_osu)
    # user_taiko = await get_user("840", mode=GameMode.taiko)
    # print(user_taiko)
    # user_fruits = await get_user("840", mode=GameMode.fruits)
    # print(user_fruits)
    # user_mania = await get_user("840", mode=GameMode.mania)
    # print(user_mania)
    beatmap_osu_attrs = await get_beatmap_attributes(351189, ruleset=GameMode.osu)
    print(beatmap_osu_attrs)
    beatmap_taiko_attrs = await get_beatmap_attributes(351189, ruleset=GameMode.taiko)
    print(beatmap_taiko_attrs)
    beatmap_fruits_attrs = await get_beatmap_attributes(351189, ruleset=GameMode.fruits)
    print(beatmap_fruits_attrs)
    beatmap_mania_attrs = await get_beatmap_attributes(351189, ruleset=GameMode.mania)
    print(beatmap_mania_attrs)
    beatmap_osu_attrs_with_dt = await get_beatmap_attributes(351189, ruleset=GameMode.osu, mods=["DT"])
    print(beatmap_osu_attrs_with_dt)
    beatmap_osu_attrs_with_hrdt = await get_beatmap_attributes(351189, ruleset=GameMode.osu, mods=["HR", "DT"])
    print(beatmap_osu_attrs_with_hrdt)


asyncio.run(test())
