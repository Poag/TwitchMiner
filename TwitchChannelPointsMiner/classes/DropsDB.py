import sqlite3
import time
from contextlib import closing

# A game's "account not linked" warning is repeated at most once per this many seconds
NOTICE_INTERVAL = 24 * 60 * 60


class DropsDB(object):
    """Remembers which drops we already tried to claim, so each is attempted only once,
    and when we last warned about a game whose account is not connected."""

    def __init__(self, path):
        self.path = path
        with closing(self.__connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS drops ("
                "drop_id TEXT PRIMARY KEY, name TEXT, game TEXT, "
                "claimed INTEGER NOT NULL, attempted_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS games ("
                "game_id TEXT PRIMARY KEY, name TEXT NOT NULL, first_seen REAL NOT NULL, "
                "last_seen REAL NOT NULL, campaigns INTEGER NOT NULL DEFAULT 0, "
                "ends_at REAL, active INTEGER NOT NULL DEFAULT 0, "
                "prioritised INTEGER NOT NULL DEFAULT 0)"
            )
            game_columns = [row[1] for row in db.execute("PRAGMA table_info(games)")]
            if "slug" not in game_columns:
                db.execute("ALTER TABLE games ADD COLUMN slug TEXT")
            # Older databases have no benefit column
            columns = [row[1] for row in db.execute("PRAGMA table_info(drops)")]
            if "benefit" not in columns:
                db.execute("ALTER TABLE drops ADD COLUMN benefit TEXT")
            db.execute(
                "CREATE TABLE IF NOT EXISTS game_notices ("
                "game TEXT PRIMARY KEY, notified_at REAL NOT NULL)"
            )

    def __connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def was_attempted(self, drop_id):
        with closing(self.__connect()) as db:
            return (
                db.execute(
                    "SELECT 1 FROM drops WHERE drop_id = ?", (drop_id,)
                ).fetchone()
                is not None
            )

    def was_claimed(self, drop_id):
        with closing(self.__connect()) as db:
            row = db.execute(
                "SELECT claimed FROM drops WHERE drop_id = ?", (drop_id,)
            ).fetchone()
            return row is not None and row[0] == 1

    def record_attempt(self, drop_id, name, game, claimed, benefit=None):
        with closing(self.__connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO drops "
                "(drop_id, name, game, claimed, attempted_at, benefit) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (drop_id, name, game, int(claimed), time.time(), benefit),
            )

    def recent(self, limit=200):
        """Newest first: [{name, benefit, game, claimed, at}], `at` in milliseconds."""
        with closing(self.__connect()) as db:
            rows = db.execute(
                "SELECT name, benefit, game, claimed, attempted_at FROM drops "
                "ORDER BY attempted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "name": name,
                "benefit": benefit,
                "game": game,
                "claimed": bool(claimed),
                "at": int(at * 1000),
            }
            for name, benefit, game, claimed, at in rows
        ]

    def record_games(self, games):
        """Remember the games that have an active drops campaign right now.

        games: [{"id", "name", "campaigns" (count), "ends_at" (epoch seconds or None)}].
        Games not in the list are kept (so they can still be prioritised) but marked inactive.
        The user's `prioritised` choice is never touched here."""
        now = time.time()
        with closing(self.__connect()) as db, db:
            db.execute("UPDATE games SET active = 0")
            for g in games:
                db.execute(
                    "INSERT INTO games (game_id, name, first_seen, last_seen, campaigns, ends_at, active, slug) "
                    "VALUES (?, ?, ?, ?, ?, ?, 1, ?) "
                    "ON CONFLICT(game_id) DO UPDATE SET name = excluded.name, "
                    "last_seen = excluded.last_seen, campaigns = excluded.campaigns, "
                    "ends_at = excluded.ends_at, active = 1, "
                    "slug = COALESCE(excluded.slug, games.slug)",
                    (str(g["id"]), g["name"], now, now, g.get("campaigns", 0), g.get("ends_at"), g.get("slug")),
                )

    def games(self):
        """Prioritised first, then games offered right now, then by name."""
        with closing(self.__connect()) as db:
            rows = db.execute(
                "SELECT game_id, name, campaigns, ends_at, active, prioritised, last_seen, slug "
                "FROM games ORDER BY prioritised DESC, active DESC, name COLLATE NOCASE"
            ).fetchall()
        return [
            {
                "id": game_id,
                "name": name,
                "campaigns": campaigns,
                "ends_at": int(ends_at * 1000) if ends_at else None,
                "active": bool(active),
                "prioritised": bool(prioritised),
                "last_seen": int(last_seen * 1000),
                "slug": slug,
            }
            for game_id, name, campaigns, ends_at, active, prioritised, last_seen, slug in rows
        ]

    def set_prioritised(self, game_id, prioritised):
        """True when the game exists (and was updated)."""
        with closing(self.__connect()) as db, db:
            cur = db.execute(
                "UPDATE games SET prioritised = ? WHERE game_id = ?",
                (int(bool(prioritised)), str(game_id)),
            )
            return cur.rowcount > 0

    def prioritised_games(self):
        """[(game_id, name)] of the games the user ticked."""
        with closing(self.__connect()) as db:
            return db.execute(
                "SELECT game_id, name FROM games WHERE prioritised = 1"
            ).fetchall()

    def should_notify_game(self, game):
        """True (and the notice is recorded) when this game was not warned about in the last day."""
        now = time.time()
        with closing(self.__connect()) as db, db:
            row = db.execute(
                "SELECT notified_at FROM game_notices WHERE game = ?", (game,)
            ).fetchone()
            if row is not None and now - row[0] < NOTICE_INTERVAL:
                return False
            db.execute(
                "INSERT OR REPLACE INTO game_notices VALUES (?, ?)", (game, now)
            )
            return True
