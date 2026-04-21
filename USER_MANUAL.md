# Podcatcher User Manual

Podcatcher is a lightweight, terminal-based podcast manager. It allows you to subscribe to RSS feeds, track new episodes, download audio files, and manage your play history directly from your command line.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Command Reference](#command-reference)
   - [Adding Feeds](#adding-feeds)
   - [Listing Subscriptions](#listing-subscriptions)
   - [Checking Status](#checking-status)
   - [Updating Feeds](#updating-feeds)
   - [Downloading Episodes](#downloading-episodes)
   - [Marking Played Status](#marking-played-status)
   - [Searching Episodes](#searching-episodes)
   - [Removing Feeds](#removing-feeds)
5. [Storage & Data](#storage--data)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

---

## Introduction

Podcatcher is designed for users who prefer the terminal for managing their media. It follows the Unix philosophy of doing one thing well: managing podcast subscriptions and downloads. It does **not** include a built-in media player; instead, it downloads episodes to your local disk so you can play them with your favorite player (e.g., `mpv`, `vlc`, `mplayer`).

---

## Installation

### Prerequisites

- **Python 3.6+**: Podcatcher uses the Python standard library only.
- **Operating System**: Linux, macOS, or any Unix-like system.

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/podcatcherpy.git
   cd podcatcherpy
   ```

2. **Make the script executable:**
   ```bash
   chmod +x podcatcher.py
   ```

3. **(Optional) Install to your PATH:**
   ```bash
   sudo cp podcatcher.py /usr/local/bin/podcatcher
   ```

---

## Quick Start

1. **Subscribe to a podcast:**
   ```bash
   podcatcher add https://feeds.megaphone.fm/darknetdiaries
   ```

2. **List your feeds:**
   ```bash
   podcatcher list
   ```

3. **Check for new episodes:**
   ```bash
   podcatcher update
   ```

4. **Download the latest episode:**
   ```bash
   podcatcher download darknetdiaries
   ```

5. **Mark an episode as played:**
   ```bash
   podcatcher mark-played darknetdiaries --episode 1
   ```

---

## Command Reference

### Adding Feeds
**Command:** `add <url> [--name SLUG]`

Subscribes to a new podcast. Podcatcher will fetch the RSS feed, parse its metadata, and store the episode list.

- **URL**: The RSS or Atom feed URL of the podcast.
- **--name SLUG**: (Optional) A custom short name for the feed. If omitted, a slug is automatically generated from the podcast title.

**Example:**
```bash
podcatcher add https://feed.syntax.fm/rss --name syntax
```

### Listing Subscriptions
**Command:** `list`

Displays a summary of all your subscribed podcasts, including their slug, episode count, last update time, and full title.

**Example:**
```bash
podcatcher list
```

### Checking Status
**Command:** `status <slug> [--count N]`

Shows detailed information about a specific podcast and its most recent episodes.

- **slug**: The short name of the podcast (from `list`).
- **--count N**: Number of recent episodes to display (default: 10).

**Markers:**
- `✔`: Episode is marked as played.
- `⬇`: Episode is downloaded to your disk.

**Example:**
```bash
podcatcher status syntax --count 5
```

### Updating Feeds
**Command:** `update [--slug SLUG] [--download]`

Refreshes the episode list for your subscriptions by re-fetching the RSS feeds.

- **--slug SLUG**: Update only the specified podcast. If omitted, all feeds are updated.
- **--download**: Automatically download any newly discovered episodes.

**Note:** If an episode is removed from the RSS feed by the publisher, Podcatcher will automatically delete the corresponding local audio file to save space.

**Example:**
```bash
podcatcher update --download
```

### Downloading Episodes
**Command:** `download [slug] [--episode N] [--all]`

Downloads audio files for episodes.

- **slug**: (Optional) Download from a specific podcast. If omitted, downloads from all feeds.
- **--episode N**: Download a specific episode by its number (as seen in `status`). Requires `slug`.
- **--all**: Download all episodes that are not yet on your disk.

**Example:**
```bash
podcatcher download syntax --episode 1
```

### Marking Played Status
**Command:** `mark-played <slug> [--episode N] [--unplayed] [-y]`

Manages the played/unplayed status of episodes.

- **--episode N**: Mark a specific episode. If omitted, marks all episodes in the feed.
- **--unplayed**: Mark as unplayed instead of played.
- **-y**: Skip confirmation when marking all episodes.

**Example:**
```bash
podcatcher mark-played darknetdiaries --episode 5
```

### Searching Episodes
**Command:** `search <query> [--limit N]`

Searches for a keyword in episode titles and descriptions across all your subscriptions.

- **query**: The search term (case-insensitive).
- **--limit N**: Maximum number of results to show per podcast.

**Example:**
```bash
podcatcher search "security"
```

### Removing Feeds
**Command:** `remove <slug> [-y]`

Unsubscribes from a podcast. **Warning:** This will delete the feed's metadata and **all** downloaded audio files for that podcast.

- **-y**: Skip confirmation prompt.

**Example:**
```bash
podcatcher remove syntax
```

---

## Storage & Data

Podcatcher stores all its data in the `~/.podcatcher/` directory:

- **`feeds.json`**: The main database containing subscription metadata and episode history.
- **`episodes/`**: A subdirectory containing folders for each podcast (named by slug), where audio files are saved.

### File Naming
Downloaded files are named based on the episode title, sanitized for your filesystem, and retain their original extension (e.g., `.mp3`, `.m4a`).

---

## Advanced Usage

### Integration with Media Players
Since Podcatcher saves files to predictable locations, you can easily play them with terminal-based players:

```bash
# Play the latest downloaded episode of Darknet Diaries using mpv
mpv ~/.podcatcher/episodes/darknetdiaries/*.mp3
```

### Automated Updates
You can set up a `cron` job to automatically update your feeds and download new episodes every night:

```cron
0 2 * * * /usr/local/bin/podcatcher update --download
```

---

## Troubleshooting

### Feed Parsing Errors
Some RSS feeds may use non-standard XML or have character encoding issues. Podcatcher uses `xml.etree.ElementTree` for parsing. If a feed fails to parse, check the URL in a browser or validator.

### 403 Forbidden Errors
Podcatcher uses a custom `User-Agent` (`Podcatcher/1.0`) to avoid being blocked by CDNs like Cloudflare that often reject default Python `urllib` requests.

### SSL/TLS Issues
If you encounter SSL errors, ensure your system's CA certificates are up to date. On some systems, you might need to run:
```bash
# Example for macOS with Homebrew Python
/Applications/Python\ 3.x/Install\ Certificates.command
```
