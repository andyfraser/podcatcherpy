# Podcatcher

A command-line podcast manager written in Python. Subscribe to RSS feeds, track new episodes, download audio files, and mark episodes as played — all from the terminal, with no third-party dependencies.

## Features

- Subscribe to any podcast via its RSS feed URL
- Refresh feeds to discover new episodes
- Download audio files with a live progress bar
- Track played/unplayed state per episode
- Search episode titles and descriptions across all feeds
- Single-file, pure Python standard library — nothing to install

## Requirements

- Python 3.6+
- Linux (or any Unix-like system)

## Installation

```bash
git clone https://github.com/yourusername/podcatcher.git
cd podcatcher
chmod +x podcatcher.py

# Optional: install system-wide
sudo cp podcatcher.py /usr/local/bin/podcatcher
```

## Quick Start

```bash
# Subscribe to a feed
podcatcher add https://feeds.megaphone.fm/darknetdiaries

# List your subscriptions
podcatcher list

# Check the latest episodes
podcatcher status darknetdiaries

# Refresh all feeds and download any new episodes
podcatcher update --download
```

## Commands

### `add` — Subscribe to a feed

```bash
podcatcher add <url> [--name SLUG]
```

Fetches the RSS feed immediately to verify it and record the episode list.

```bash
podcatcher add https://feeds.megaphone.fm/darknetdiaries
podcatcher add https://feed.syntax.fm/rss --name syntax
```

`--name` lets you choose a short slug instead of one derived from the podcast title. The slug is used in all other commands.

---

### `list` — List subscriptions

```bash
podcatcher list
```

Prints a table of all subscribed feeds showing slug, episode count, last updated date, and title.

---

### `status` — Show feed details

```bash
podcatcher status <slug> [--count N]
```

Shows metadata for a feed and a numbered list of recent episodes. Each episode line includes played (`✔`) and downloaded (`⬇`) markers.

```bash
podcatcher status darknetdiaries
podcatcher status darknetdiaries --count 25
```

---

### `update` — Refresh feeds

```bash
podcatcher update [--slug SLUG] [--download]
```

Re-fetches one or all feeds to discover new episodes. Played flags and local file paths are preserved across updates.

```bash
podcatcher update                              # refresh all feeds
podcatcher update --slug syntax               # refresh one feed
podcatcher update --download                  # refresh all and download new episodes
podcatcher update --slug syntax --download    # refresh one feed and download new episodes
```

---

### `download` — Download episode audio

```bash
podcatcher download [SLUG] [--episode N] [--all]
```

Downloads audio files to `~/.podcatcher/episodes/<slug>/`. Files are named after the episode title and keep their original extension. A progress bar is shown for each file. Already-downloaded files are skipped.

By default, only episodes that have never been downloaded are queued.

```bash
podcatcher download syntax              # download new episodes from one feed
podcatcher download syntax --episode 7  # download a specific episode by number
podcatcher download syntax --all        # download everything not yet on disk
podcatcher download                     # download new episodes from all feeds
```

---

### `mark-played` — Mark episodes played or unplayed

```bash
podcatcher mark-played <slug> [--episode N] [--unplayed] [-y]
```

```bash
podcatcher mark-played darknetdiaries              # mark all episodes played
podcatcher mark-played darknetdiaries -y           # skip confirmation prompt
podcatcher mark-played darknetdiaries --episode 12 # mark one episode played
podcatcher mark-played darknetdiaries --unplayed   # mark all episodes unplayed
```

---

### `remove` — Unsubscribe from a feed

```bash
podcatcher remove <slug> [-y]
```

Removes the feed from the subscription database. Downloaded audio files on disk are **not** deleted — remove `~/.podcatcher/episodes/<slug>/` manually if needed.

```bash
podcatcher remove syntax
podcatcher remove syntax -y   # skip confirmation
```

---

### `search` — Search episodes

```bash
podcatcher search <query> [--limit N]
```

Searches episode titles and descriptions across all subscribed feeds. Results are grouped by feed.

```bash
podcatcher search "javascript"
podcatcher search "security" --limit 5
```

---

### `help` — Command reference

```bash
podcatcher help              # full overview of all commands
podcatcher help download     # detailed syntax and examples for one command
```

## Data Storage

All data is stored in `~/.podcatcher/`:

```
~/.podcatcher/
  feeds.json              subscription database (JSON, human-readable)
  episodes/
    <slug>/               downloaded audio files for each feed
```

To back up your subscriptions and play history, copy `feeds.json`. To completely reset, delete the `~/.podcatcher/` directory.

## Episode Status Markers

The `status` command shows two indicators next to each episode:

| Marker | Meaning |
|--------|---------|
| `✔` | Episode has been marked as played |
| `⬇` | Audio file has been downloaded to disk |

## License

MIT
