# Changelog

All notable changes to TwitchMiner. The format follows [Keep a Changelog](https://keepachangelog.com/), and versions follow [Semantic Versioning](https://semver.org/). TwitchMiner is a fork of [Twitch Channel Points Miner v2](https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2); see [Credits and license](README.md#credits-and-license).

## [Unreleased]

### Fixed
- The drops sync could end silently: when Twitch answered the drops dashboard request with an error (`data: null`), the sync thread crashed, which stopped drop claiming and left **Games with drops** empty until the next restart. The response is now read safely, the error is logged, and any unexpected error in the sync is logged and retried instead of ending the thread.
- Games are now recorded from your inventory, the drops dashboard and the campaign details, so one failing request can't leave the list empty. Each sync logs how many campaigns and games it found.

## [1.1.0] - 2026-10-18

### Added
- **Prioritise games for drops.** Every game with an active drops campaign is recorded in the drops database, and a new **Games with drops** table on the analytics page lets you tick the games to watch first. `TCPM_PRIORITY_GAMES` does the same from the environment. When the miner picks streamers for the `DROPS` priority, those playing a prioritised game come first.
- **Drops table** on the analytics page: every drop the miner tried to claim, with time, drop, game and claimed or failed.
- **Live Log panel** on the analytics page, served from memory at the console log level, so it works without a log file and restarts cleanly with the miner.
- **Currently watching** border: the streamers the miner is sending watch events for are outlined in green in the analytics streamer list.
- `CONTRIBUTING.md` rewritten for this project, and an example [`compose.yaml`](compose.yaml).

### Changed
- Docker is the only supported way to run TwitchMiner; the run-from-source, Windows and Termux instructions were removed.
- The README no longer mentions Moments, which Twitch retired.

### Fixed
- `TCPM_FOLLOWERS_ORDER` was ignored, and a failed follow-list request returned an empty list without saying why. Failures are now logged.
- The analytics log panel used to stop updating (emoji offset drift, rotated or renamed log files).

### Removed
- `CODE_OF_CONDUCT.md`.

## [1.0.0] - 2026-10-09

First TwitchMiner release, forked from rdavydov's Twitch Channel Points Miner v2.

### Added
- Configuration entirely through `TCPM_*` environment variables (`.env.example`), started with `python -m TwitchChannelPointsMiner`.
- One data folder, `TCPM_DATA_DIR`, holding `cookies/`, `database/`, `logs/` and `analytics/`, so Docker needs a single volume.
- Each drop is claimed **once only**, tracked in a per-account database. Drops for a game whose account is not connected are skipped, with a daily warning and a countdown to the end of the campaign.
- Multi-arch (`amd64`, `arm64`) images on GHCR built on native runners: `latest` on `main`, version tags, and a monthly rebuild.
- New icon and TwitchMiner branding, with credits and the GPL-3.0 notice for the upstream projects.
- Redesigned analytics page: light and dark themes, card layout, no external UI frameworks.

### Changed
- Lower idle CPU and memory use: no busy IRC loop, analytics data kept in memory and written compactly, pandas imported lazily, no needless drops polling.
- Smaller Docker image on Python 3.12 slim (no compilers needed).
- The version check and asset downloads now use this repository instead of the upstream one.

### Removed
- Betting and predictions, with all their settings, events and colours.
- `run.py` / `example.py` configuration, the Docker Hub image, `arm/v7` builds, and the upstream traffic and clone badge workflows.
