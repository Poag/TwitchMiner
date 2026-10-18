"""Build a TwitchChannelPointsMiner from environment variables (see README, "Configuration").

All variables are prefixed with ``TCPM_``. Booleans accept true/false, 1/0, yes/no, on/off.
Lists are comma separated. Notifiers are only enabled when their required variables are set.
"""

import logging
import os
import platform
import sys

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.classes.Gotify import Gotify
from TwitchChannelPointsMiner.classes.Matrix import Matrix
from TwitchChannelPointsMiner.classes.Pushover import Pushover
from TwitchChannelPointsMiner.classes.Settings import Events, FollowersOrder, Priority
from TwitchChannelPointsMiner.classes.Telegram import Telegram
from TwitchChannelPointsMiner.classes.Webhook import Webhook
from TwitchChannelPointsMiner.logger import ColorPalette, LoggerSettings

PREFIX = "TCPM_"

DEFAULT_EVENTS = "STREAMER_ONLINE,STREAMER_OFFLINE,CHAT_MENTION"

STREAMER_BOOL_KEYS = [
    "follow_raid",
    "claim_drops",
    "claim_moments",
    "watch_streak",
    "community_goals",
]


class ConfigError(Exception):
    pass


class Env:
    def __init__(self, environ):
        self.environ = environ

    def get(self, name, default=None):
        value = self.environ.get(PREFIX + name)
        if value is None or value.strip() == "":
            return default
        return value.strip()

    def has(self, *names):
        return all(self.get(n) is not None for n in names)

    def bool(self, name, default=None):
        return parse_bool(PREFIX + name, self.get(name), default)

    def int(self, name, default=None):
        value = self.get(name)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ConfigError(f"{PREFIX}{name} must be an integer, got '{value}'")

    def list(self, name, default=""):
        return [v.strip() for v in (self.get(name, default) or "").split(",") if v.strip()]


def parse_bool(label, value, default=None):
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in ("true", "1", "yes", "on"):
        return True
    if lowered in ("false", "0", "no", "off"):
        return False
    raise ConfigError(f"{label} must be true or false, got '{value}'")


def parse_enum(label, value, enum):
    try:
        return enum[value.strip().upper()]
    except KeyError:
        allowed = ", ".join(e.name for e in enum)
        raise ConfigError(f"{label} has invalid value '{value}'. Allowed: {allowed}")


def parse_log_level(label, value, default):
    if value is None:
        return default
    level = logging.getLevelName(value.upper())
    if not isinstance(level, int):
        raise ConfigError(f"{label} must be a logging level (DEBUG, INFO, ...), got '{value}'")
    return level


def parse_events(env, name, default=DEFAULT_EVENTS):
    events = []
    for item in env.list(name, default):
        event = Events.get(item.upper())
        if event is None:
            allowed = ", ".join(e.name for e in Events)
            raise ConfigError(f"{PREFIX}{name} has unknown event '{item}'. Allowed: {allowed}")
        events.append(event)
    return events


def build_notifiers(env):
    notifiers = {}
    if env.has("TELEGRAM_CHAT_ID", "TELEGRAM_TOKEN"):
        notifiers["telegram"] = Telegram(
            chat_id=env.int("TELEGRAM_CHAT_ID"),
            token=env.get("TELEGRAM_TOKEN"),
            events=parse_events(env, "TELEGRAM_EVENTS"),
            disable_notification=env.bool("TELEGRAM_DISABLE_NOTIFICATION", False),
        )
    if env.has("DISCORD_WEBHOOK_API"):
        notifiers["discord"] = Discord(
            webhook_api=env.get("DISCORD_WEBHOOK_API"),
            events=parse_events(env, "DISCORD_EVENTS"),
        )
    if env.has("WEBHOOK_ENDPOINT"):
        notifiers["webhook"] = Webhook(
            endpoint=env.get("WEBHOOK_ENDPOINT"),
            method=env.get("WEBHOOK_METHOD", "GET"),
            events=parse_events(env, "WEBHOOK_EVENTS"),
        )
    if env.has("MATRIX_USERNAME", "MATRIX_PASSWORD", "MATRIX_HOMESERVER", "MATRIX_ROOM_ID"):
        notifiers["matrix"] = Matrix(
            username=env.get("MATRIX_USERNAME"),
            password=env.get("MATRIX_PASSWORD"),
            homeserver=env.get("MATRIX_HOMESERVER"),
            room_id=env.get("MATRIX_ROOM_ID"),
            events=parse_events(env, "MATRIX_EVENTS"),
        )
    if env.has("PUSHOVER_USERKEY", "PUSHOVER_TOKEN"):
        notifiers["pushover"] = Pushover(
            userkey=env.get("PUSHOVER_USERKEY"),
            token=env.get("PUSHOVER_TOKEN"),
            priority=env.int("PUSHOVER_PRIORITY", 0),
            sound=env.get("PUSHOVER_SOUND", "pushover"),
            events=parse_events(env, "PUSHOVER_EVENTS", "CHAT_MENTION,DROP_CLAIM"),
        )
    if env.has("GOTIFY_ENDPOINT"):
        notifiers["gotify"] = Gotify(
            endpoint=env.get("GOTIFY_ENDPOINT"),
            priority=env.int("GOTIFY_PRIORITY", 8),
            events=parse_events(env, "GOTIFY_EVENTS"),
        )
    return notifiers


def build_color_palette(env):
    colors = {}
    for event in Events:
        value = env.get(f"COLOR_{event.name}")
        if value is not None:
            colors[event.name] = value
    return ColorPalette(**colors)


def build_logger_settings(env, username):
    kwargs = dict(
        save=env.bool("LOG_SAVE", True),
        less=env.bool("LOG_LESS", False),
        console_level=parse_log_level(
            PREFIX + "LOG_CONSOLE_LEVEL", env.get("LOG_CONSOLE_LEVEL"), logging.INFO
        ),
        console_username=env.bool("LOG_CONSOLE_USERNAME", False),
        time_zone=env.get("TIME_ZONE", ""),
        file_level=parse_log_level(
            PREFIX + "LOG_FILE_LEVEL", env.get("LOG_FILE_LEVEL"), logging.DEBUG
        ),
        emoji=env.bool("LOG_EMOJI", platform.system() != "Windows"),
        colored=env.bool("LOG_COLORED", True),
        auto_clear=env.bool("LOG_AUTO_CLEAR", True),
        color_palette=build_color_palette(env),
    )
    kwargs.update(build_notifiers(env))
    return LoggerSettings(**kwargs)


def parse_streamer_settings(label, values, base=None):
    """values: dict of key -> string. Returns a StreamerSettings with only those keys set."""
    settings = StreamerSettings()
    for key, value in values.items():
        key = key.strip().lower()
        if key in STREAMER_BOOL_KEYS:
            setattr(settings, key, parse_bool(f"{label} {key}", value))
        elif key == "chat":
            settings.chat = parse_enum(f"{label} chat", value, ChatPresence)
        else:
            allowed = ", ".join(STREAMER_BOOL_KEYS + ["chat"])
            raise ConfigError(f"{label} has unknown streamer setting '{key}'. Allowed: {allowed}")
    return settings


def build_default_streamer_settings(env):
    values = {}
    for key in STREAMER_BOOL_KEYS + ["chat"]:
        value = env.get(key.upper())
        if value is not None:
            values[key] = value
    return parse_streamer_settings(PREFIX + "<setting>", values)


def parse_streamers(env):
    """TCPM_STREAMERS="name,name2:follow_raid=false+watch_streak=true,name3"."""
    streamers = []
    for entry in env.list("STREAMERS"):
        name, _, overrides = entry.partition(":")
        name = name.strip()
        if not overrides:
            streamers.append(name)
            continue
        values = {}
        for pair in overrides.split("+"):
            key, sep, value = pair.partition("=")
            if not sep:
                raise ConfigError(
                    f"{PREFIX}STREAMERS entry '{entry}': expected key=value, got '{pair}'"
                )
            values[key] = value
        streamers.append(
            Streamer(name, settings=parse_streamer_settings(f"{PREFIX}STREAMERS '{name}'", values))
        )
    return streamers


def from_env(environ=None):
    """Returns (miner, mine_kwargs, analytics_kwargs_or_None)."""
    env = Env(os.environ if environ is None else environ)

    username = env.get("USERNAME")
    if not username:
        raise ConfigError(f"{PREFIX}USERNAME is required")

    priority = [
        parse_enum(PREFIX + "PRIORITY", p, Priority)
        for p in env.list("PRIORITY", "STREAK,DROPS,ORDER")
    ]

    enable_analytics = env.bool("ENABLE_ANALYTICS", False)

    miner = TwitchChannelPointsMiner(
        username=username,
        password=env.get("PASSWORD"),
        claim_drops_startup=env.bool("CLAIM_DROPS_STARTUP", False),
        priority=priority,
        priority_games=env.list("PRIORITY_GAMES"),
        enable_analytics=enable_analytics,
        disable_ssl_cert_verification=env.bool("DISABLE_SSL_CERT_VERIFICATION", False),
        disable_at_in_nickname=env.bool("DISABLE_AT_IN_NICKNAME", False),
        logger_settings=build_logger_settings(env, username),
        streamer_settings=build_default_streamer_settings(env),
    )

    mine_kwargs = dict(
        streamers=parse_streamers(env),
        blacklist=env.list("BLACKLIST"),
        followers=env.bool("FOLLOWERS", False),
        followers_order=parse_enum(
            PREFIX + "FOLLOWERS_ORDER", env.get("FOLLOWERS_ORDER", "ASC"), FollowersOrder
        ),
    )

    analytics_kwargs = None
    if enable_analytics:
        analytics_kwargs = dict(
            host=env.get("ANALYTICS_HOST", "127.0.0.1"),
            port=env.int("ANALYTICS_PORT", 5000),
            refresh=env.int("ANALYTICS_REFRESH", 5),
            days_ago=env.int("ANALYTICS_DAYS_AGO", 7),
        )
    return miner, mine_kwargs, analytics_kwargs


def main():
    try:
        miner, mine_kwargs, analytics_kwargs = from_env()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(2)
    if analytics_kwargs is not None:
        miner.analytics(**analytics_kwargs)
    else:
        logging.getLogger(__name__).info(
            "Analytics web page is off. Set TCPM_ENABLE_ANALYTICS=true to serve it on port 5000."
        )
    miner.mine(**mine_kwargs)
