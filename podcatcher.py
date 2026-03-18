#!/usr/bin/env python3
"""
Podcatcher - A command-line podcast manager
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

USER_AGENT = "Podcatcher/1.0 +https://github.com/podcatcher"


def open_url(url, timeout=30):
    """Open a URL with a podcast-friendly User-Agent to avoid CDN 403 rejections."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    return urlopen(req, timeout=timeout)

# ─── Config & Storage ──────────────────────────────────────────────────────────

DATA_DIR = os.path.expanduser("~/.podcatcher")
FEEDS_FILE = os.path.join(DATA_DIR, "feeds.json")
EPISODES_DIR = os.path.join(DATA_DIR, "episodes")


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(EPISODES_DIR, exist_ok=True)


def episode_dir(slug):
    path = os.path.join(EPISODES_DIR, slug)
    os.makedirs(path, exist_ok=True)
    return path


def safe_filename(title, url):
    """Derive a filesystem-safe filename from the episode title, keeping the URL extension."""
    import re
    ext = os.path.splitext(urlparse(url).path)[1] or ".mp3"
    name = re.sub(r"[^\w\s-]", "", title.lower())
    name = re.sub(r"[\s_-]+", "-", name).strip("-")[:80]
    return name + ext


def download_episode(ep, slug):
    """Download a single episode. Returns local path on success, None on failure."""
    url = ep["audio_url"]
    filename = safe_filename(ep["title"], url)
    dest_dir = episode_dir(slug)
    dest = os.path.join(dest_dir, filename)

    if os.path.exists(dest):
        return dest  # already present

    print(f"  ↓ {ep['title'][:55]}")
    print(f"    {url}")

    try:
        with open_url(url, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk = 64 * 1024  # 64 KB
            with open(dest, "wb") as f:
                while True:
                    buf = resp.read(chunk)
                    if not buf:
                        break
                    f.write(buf)
                    downloaded += len(buf)
                    if total:
                        pct = downloaded * 100 // total
                        mb_done = downloaded / 1_048_576
                        mb_total = total / 1_048_576
                        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                        print(f"\r    [{bar}] {pct:3d}%  {mb_done:.1f}/{mb_total:.1f} MB", end="", flush=True)
                    else:
                        mb_done = downloaded / 1_048_576
                        print(f"\r    {mb_done:.1f} MB downloaded…", end="", flush=True)
        print()  # newline after progress bar
        return dest

    except HTTPError as e:
        print(f"\n    [ERROR] HTTP {e.code}: {e.reason}")
    except URLError as e:
        print(f"\n    [ERROR] {e.reason}")
    except Exception as e:
        print(f"\n    [ERROR] {e}")

    # Clean up partial file
    if os.path.exists(dest):
        os.remove(dest)
    return None


def load_feeds():
    if not os.path.exists(FEEDS_FILE):
        return {}
    with open(FEEDS_FILE, "r") as f:
        return json.load(f)


def save_feeds(feeds):
    with open(FEEDS_FILE, "w") as f:
        json.dump(feeds, f, indent=2)


# ─── RSS Parsing ───────────────────────────────────────────────────────────────

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def fetch_feed_xml(url):
    try:
        with open_url(url, timeout=15) as resp:
            return resp.read()
    except HTTPError as e:
        print(f"  [ERROR] HTTP {e.code}: {e.reason}")
        return None
    except URLError as e:
        print(f"  [ERROR] Could not reach URL: {e.reason}")
        return None
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def parse_feed(xml_bytes):
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  [ERROR] Failed to parse XML: {e}")
        return None

    channel = root.find("channel")
    if channel is None:
        print("  [ERROR] No <channel> found in feed.")
        return None

    title = _text(channel, "title") or "Untitled Podcast"
    description = _text(channel, "description") or ""
    link = _text(channel, "link") or ""
    last_build = _text(channel, "lastBuildDate") or ""
    image_url = ""
    img_tag = channel.find("image")
    if img_tag is not None:
        image_url = _text(img_tag, "url") or ""
    if not image_url:
        image_url = _attr(channel, "itunes:image", "href") or ""

    episodes = []
    for item in channel.findall("item"):
        ep = parse_episode(item)
        if ep:
            episodes.append(ep)

    return {
        "title": title,
        "description": description[:200],
        "link": link,
        "last_build": last_build,
        "image_url": image_url,
        "episodes": episodes,
    }


def parse_episode(item):
    title = _text(item, "title") or "Untitled Episode"
    pub_date = _text(item, "pubDate") or ""
    guid = _text(item, "guid") or ""
    description = _text(item, "description") or ""
    duration = _text(item, "itunes:duration") or ""

    enclosure = item.find("enclosure")
    audio_url = ""
    file_size = 0
    mime_type = ""
    if enclosure is not None:
        audio_url = enclosure.get("url", "")
        file_size = int(enclosure.get("length", 0) or 0)
        mime_type = enclosure.get("type", "")

    if not audio_url:
        return None

    return {
        "title": title,
        "pub_date": pub_date,
        "guid": guid or audio_url,
        "audio_url": audio_url,
        "file_size": file_size,
        "mime_type": mime_type,
        "duration": duration,
        "description": (description[:300]).strip(),
    }


def _text(element, tag):
    child = element.find(tag, NS)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _attr(element, tag, attr):
    child = element.find(tag, NS)
    if child is not None:
        return child.get(attr, "")
    return ""


# ─── Feed slug helpers ─────────────────────────────────────────────────────────

def slugify(title):
    import re
    s = title.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:40] or "podcast"


def unique_slug(slug, feeds):
    if slug not in feeds:
        return slug
    i = 2
    while f"{slug}-{i}" in feeds:
        i += 1
    return f"{slug}-{i}"


# ─── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args):
    url = args.url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        print(f"[ERROR] URL must start with http:// or https://")
        sys.exit(1)

    feeds = load_feeds()

    # Check for duplicate URL
    for slug, feed in feeds.items():
        if feed["url"] == url:
            print(f"[INFO] Feed already exists as '{slug}': {feed['meta']['title']}")
            return

    print(f"Fetching feed from {url} ...")
    xml_bytes = fetch_feed_xml(url)
    if xml_bytes is None:
        sys.exit(1)

    meta = parse_feed(xml_bytes)
    if meta is None:
        sys.exit(1)

    episodes = meta.pop("episodes")
    slug = args.name if args.name else slugify(meta["title"])
    slug = unique_slug(slug, feeds)

    known_guids = [ep["guid"] for ep in episodes]

    feeds[slug] = {
        "url": url,
        "added": datetime.now().isoformat(timespec="seconds"),
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "meta": meta,
        "episodes": episodes,
        "known_guids": known_guids,
    }

    save_feeds(feeds)
    ep_count = len(episodes)
    print(f"\n  ✔ Added '{meta['title']}' as [{slug}]")
    print(f"    {ep_count} episode(s) found.")


def cmd_list(args):
    feeds = load_feeds()
    if not feeds:
        print("No feeds. Add one with:  podcatcher add <url>")
        return

    col_w = max(len(s) for s in feeds) + 2
    print(f"\n{'SLUG':<{col_w}} {'EPISODES':>9}  {'LAST UPDATED':<22}  TITLE")
    print("─" * 90)
    for slug, feed in feeds.items():
        ep_count = len(feed.get("episodes", []))
        updated = feed.get("last_updated", "")[:19]
        title = feed["meta"]["title"][:45]
        print(f"{slug:<{col_w}} {ep_count:>9}  {updated:<22}  {title}")
    print()


def cmd_status(args):
    feeds = load_feeds()
    slug = args.slug

    if slug not in feeds:
        print(f"[ERROR] No feed with slug '{slug}'. Run 'list' to see all feeds.")
        sys.exit(1)

    feed = feeds[slug]
    meta = feed["meta"]
    episodes = feed.get("episodes", [])

    print(f"\n{'═'*60}")
    print(f"  {meta['title']}")
    print(f"{'═'*60}")
    print(f"  Slug       : {slug}")
    print(f"  URL        : {feed['url']}")
    print(f"  Added      : {feed.get('added', '')}")
    print(f"  Updated    : {feed.get('last_updated', '')}")
    print(f"  Episodes   : {len(episodes)}")
    if meta.get("description"):
        desc = meta["description"][:120]
        print(f"  Description: {desc}")
    print()

    if not episodes:
        print("  No episodes found.")
        return

    played_count = sum(1 for ep in episodes if ep.get("played"))
    print(f"  Played     : {played_count} / {len(episodes)}")
    print()

    count = min(args.count if args.count else 10, len(episodes))
    print(f"  Latest {count} episode(s):")
    print(f"  {'─'*56}")
    for i, ep in enumerate(episodes[:count], 1):
        pub = ep.get("pub_date", "")[:22]
        dur = f" [{ep['duration']}]" if ep.get("duration") else ""
        size_mb = f" {ep['file_size']//1_000_000}MB" if ep.get("file_size") else ""
        played_marker = " ✔" if ep.get("played") else "  "
        dl_marker = " ⬇" if ep.get("local_path") and os.path.exists(ep["local_path"]) else "  "
        print(f"  {i:>3}.{played_marker}{dl_marker} {ep['title'][:48]}")
        print(f"        {pub}{dur}{size_mb}")
    print()


def cmd_update(args):
    feeds = load_feeds()
    if not feeds:
        print("No feeds to update.")
        return

    if args.slug:
        if args.slug not in feeds:
            print(f"[ERROR] No feed with slug '{args.slug}'.")
            sys.exit(1)
        targets = {args.slug: feeds[args.slug]}
    else:
        targets = feeds

    total_new = 0
    for slug, feed in targets.items():
        print(f"\nUpdating [{slug}] — {feed['meta']['title']}")
        print(f"  URL: {feed['url']}")

        xml_bytes = fetch_feed_xml(feed["url"])
        if xml_bytes is None:
            print("  [SKIP] Could not fetch feed.")
            continue

        parsed = parse_feed(xml_bytes)
        if parsed is None:
            print("  [SKIP] Could not parse feed.")
            continue

        new_episodes = parsed.pop("episodes")
        known_guids = set(feed.get("known_guids", []))
        fresh = [ep for ep in new_episodes if ep["guid"] not in known_guids]

        # Preserve played and download state from existing episodes
        played_guids = {
            ep["guid"]
            for ep in feed.get("episodes", [])
            if ep.get("played")
        }
        local_paths = {
            ep["guid"]: ep["local_path"]
            for ep in feed.get("episodes", [])
            if ep.get("local_path")
        }
        for ep in new_episodes:
            ep["played"] = ep["guid"] in played_guids
            ep["local_path"] = local_paths.get(ep["guid"], "")

        feeds[slug]["meta"].update(parsed)
        feeds[slug]["episodes"] = new_episodes
        feeds[slug]["known_guids"] = [ep["guid"] for ep in new_episodes]
        feeds[slug]["last_updated"] = datetime.now().isoformat(timespec="seconds")

        if fresh:
            print(f"  ✔ {len(fresh)} new episode(s):")
            for ep in fresh[:5]:
                print(f"    + {ep['title'][:60]}")
            if len(fresh) > 5:
                print(f"    … and {len(fresh) - 5} more")

            if args.download:
                print(f"\n  Downloading {len(fresh)} new episode(s)…")
                for ep in fresh:
                    local = download_episode(ep, slug)
                    if local:
                        ep["local_path"] = local
                        print(f"    ✔ Saved to {local}")
        else:
            print("  ✔ No new episodes.")

        total_new += len(fresh)

    save_feeds(feeds)
    print(f"\nDone. {total_new} new episode(s) across {len(targets)} feed(s).\n")


def cmd_remove(args):
    feeds = load_feeds()
    slug = args.slug
    if slug not in feeds:
        print(f"[ERROR] No feed with slug '{slug}'.")
        sys.exit(1)

    title = feeds[slug]["meta"]["title"]
    if not args.yes:
        confirm = input(f"Remove '{title}' [{slug}]? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    del feeds[slug]
    save_feeds(feeds)
    print(f"  ✔ Removed '{title}'.")


def cmd_search(args):
    feeds = load_feeds()
    query = args.query.lower()
    found = False

    for slug, feed in feeds.items():
        matches = [
            ep for ep in feed.get("episodes", [])
            if query in ep["title"].lower() or query in ep.get("description", "").lower()
        ]
        if matches:
            found = True
            print(f"\n[{slug}] {feed['meta']['title']}")
            for ep in matches[:args.limit]:
                print(f"  • {ep['title'][:70]}")
                print(f"    {ep.get('pub_date','')[:22]}")

    if not found:
        print(f"No episodes matched '{args.query}'.")


def cmd_mark_played(args):
    feeds = load_feeds()
    slug = args.slug

    if slug not in feeds:
        print(f"[ERROR] No feed with slug '{slug}'. Run 'list' to see all feeds.")
        sys.exit(1)

    episodes = feeds[slug].get("episodes", [])
    if not episodes:
        print("  No episodes found.")
        return

    title = feeds[slug]["meta"]["title"]

    if args.episode:
        # Mark a single episode by 1-based index (as shown in status)
        idx = args.episode - 1
        if idx < 0 or idx >= len(episodes):
            print(f"[ERROR] Episode number must be between 1 and {len(episodes)}.")
            sys.exit(1)
        ep = episodes[idx]
        if ep.get("played") and not args.unplayed:
            print(f"  Already marked played: {ep['title'][:60]}")
            return
        ep["played"] = not args.unplayed
        action = "unplayed" if args.unplayed else "played"
        print(f"  ✔ Marked {action}: {ep['title'][:60]}")
    else:
        # Mark all episodes
        action = "unplayed" if args.unplayed else "played"
        if not args.yes:
            prompt = f"Mark all {len(episodes)} episodes of '{title}' as {action}? [y/N] "
            if input(prompt).strip().lower() != "y":
                print("Aborted.")
                return
        for ep in episodes:
            ep["played"] = not args.unplayed
        print(f"  ✔ Marked all {len(episodes)} episode(s) as {action}.")

    save_feeds(feeds)


def cmd_download(args):
    feeds = load_feeds()

    if args.slug:
        if args.slug not in feeds:
            print(f"[ERROR] No feed with slug '{args.slug}'.")
            sys.exit(1)
        targets = {args.slug: feeds[args.slug]}
    else:
        targets = feeds

    if not targets:
        print("No feeds. Add one with:  podcatcher add <url>")
        return

    total_ok = total_fail = 0

    for slug, feed in targets.items():
        episodes = feed.get("episodes", [])
        if not episodes:
            continue

        if args.episode:
            # Single episode by 1-based index
            if args.slug is None:
                print("[ERROR] --episode requires a slug argument.")
                sys.exit(1)
            idx = args.episode - 1
            if idx < 0 or idx >= len(episodes):
                print(f"[ERROR] Episode number must be between 1 and {len(episodes)}.")
                sys.exit(1)
            queue = [episodes[idx]]
        elif args.all:
            # Everything not yet downloaded
            queue = [ep for ep in episodes if not ep.get("local_path") or not os.path.exists(ep["local_path"])]
        else:
            # Default: new episodes (no local file)
            queue = [ep for ep in episodes if not ep.get("local_path") or not os.path.exists(ep["local_path"])]
            # Treat "new" as those without a local_path recorded at all
            queue = [ep for ep in episodes if not ep.get("local_path")]

        if not queue:
            print(f"[{slug}] Nothing to download.")
            continue

        print(f"\n[{slug}] {feed['meta']['title']}  —  {len(queue)} episode(s) to download")

        for ep in queue:
            local = download_episode(ep, slug)
            if local:
                ep["local_path"] = local
                print(f"    ✔ Saved: {local}")
                total_ok += 1
            else:
                total_fail += 1

    save_feeds(feeds)
    print(f"\nDownload complete: {total_ok} succeeded, {total_fail} failed.\n")


def cmd_help(args):
    topic = args.topic

    # ── full reference ──────────────────────────────────────────────────────
    HELP = {
        "add": """\
  add <url> [--name SLUG]

  Subscribe to a new podcast by its RSS feed URL. Podcatcher fetches the feed
  immediately to verify it and store the current episode list.

  Arguments:
    url           RSS/Atom feed URL (must begin with http:// or https://)

  Options:
    --name SLUG   Give the feed a custom short name instead of the one derived
                  from the podcast title. The name is used as the slug in all
                  other commands.

  Examples:
    podcatcher add https://feeds.megaphone.fm/darknetdiaries
    podcatcher add https://feed.syntax.fm/rss
    podcatcher add https://feed.syntax.fm/rss --name syntax
""",

        "list": """\
  list

  Print a summary table of every subscribed feed showing its slug, total
  episode count, date last refreshed, and title.

  Examples:
    podcatcher list
""",

        "status": """\
  status <slug> [--count N]

  Show detailed information about a single feed and a numbered list of its
  most recent episodes. Each episode line displays:
    ✔  — episode has been marked played
    ⬇  — episode file has been downloaded to disk

  Arguments:
    slug          Feed slug (shown in the leftmost column of 'list')

  Options:
    --count N     How many recent episodes to show (default: 10)

  Examples:
    podcatcher status darknetdiaries
    podcatcher status darknetdiaries --count 25
    podcatcher status syntax --count 3
""",

        "update": """\
  update [--slug SLUG] [--download]

  Re-fetch one or all feeds to discover new episodes. Without --slug every
  subscribed feed is refreshed. Played flags and local file paths recorded
  from previous runs are preserved across the update.

  Options:
    --slug SLUG   Refresh only this feed
    --download    After updating, immediately download any newly found episodes

  Examples:
    podcatcher update
    podcatcher update --slug syntax
    podcatcher update --download
    podcatcher update --slug darknetdiaries --download
""",

        "download": """\
  download [SLUG] [--episode N] [--all]

  Download episode audio files to ~/.podcatcher/episodes/<slug>/.
  Files are named after the episode title and keep their original extension
  (.mp3, .m4a, etc.). A progress bar is shown for each file.

  By default only episodes that have never been downloaded are queued.
  Already-downloaded files are skipped even if --all is passed.

  Arguments:
    SLUG          Feed slug. Omit to download from every subscribed feed.

  Options:
    --episode N   Download only episode number N (as shown in 'status').
                  Requires a slug to be given.
    --all         Download every episode not already on disk, not just new ones.

  Examples:
    podcatcher download syntax
    podcatcher download syntax --episode 7
    podcatcher download syntax --all
    podcatcher download
    podcatcher download --all
""",

        "mark-played": """\
  mark-played <slug> [--episode N] [--unplayed] [-y]

  Mark episodes of a feed as played or unplayed. The played state is shown
  as a ✔ marker in 'status' output and is preserved across feed updates.

  Arguments:
    slug          Feed slug

  Options:
    --episode N   Mark only episode number N (as shown in 'status').
                  Omit to mark every episode in the feed.
    --unplayed    Reverse the operation — mark as unplayed instead of played.
    -y, --yes     Skip the confirmation prompt when marking all episodes.

  Examples:
    podcatcher mark-played darknetdiaries
    podcatcher mark-played darknetdiaries -y
    podcatcher mark-played darknetdiaries --episode 12
    podcatcher mark-played darknetdiaries --unplayed
    podcatcher mark-played darknetdiaries --episode 3 --unplayed
""",

        "remove": """\
  remove <slug> [-y]

  Unsubscribe from a feed. The feed's metadata and episode list are deleted
  from ~/.podcatcher/feeds.json. Downloaded audio files on disk are NOT
  removed — delete ~/.podcatcher/episodes/<slug>/ manually if needed.

  Arguments:
    slug          Feed slug

  Options:
    -y, --yes     Skip the confirmation prompt.

  Examples:
    podcatcher remove syntax
    podcatcher remove syntax -y
""",

        "search": """\
  search <query> [--limit N]

  Search episode titles and descriptions across every subscribed feed.
  Results are grouped by feed.

  Arguments:
    query         Search term (case-insensitive)

  Options:
    --limit N     Maximum results to show per feed (default: 10)

  Examples:
    podcatcher search "javascript"
    podcatcher search "security" --limit 5
    podcatcher search linux
""",
    }

    W = 60

    if topic:
        key = topic.lower().replace("_", "-")
        if key not in HELP:
            print(f"[ERROR] Unknown command '{topic}'. "
                  f"Available: {', '.join(HELP)}")
            sys.exit(1)
        print(f"\n{'═'*W}")
        print(f"  podcatcher {key}")
        print(f"{'═'*W}")
        print(HELP[key])
        return

    # ── overview ────────────────────────────────────────────────────────────
    print(f"""
{'═'*W}
  Podcatcher  —  command-line podcast manager
{'═'*W}

  Data is stored in ~/.podcatcher/
    feeds.json          subscription database
    episodes/<slug>/    downloaded audio files

  Episode markers shown in 'status':
    ✔  played      ⬇  downloaded to disk

  Usage:  podcatcher <command> [options]

{'─'*W}
  COMMAND        SUMMARY
{'─'*W}
  add            Subscribe to a feed by RSS URL
  list           List all subscribed feeds
  status         Show feed details and recent episodes
  update         Refresh feeds, optionally download new episodes
  download       Download episode audio files
  mark-played    Mark episodes as played or unplayed
  remove         Unsubscribe from a feed
  search         Search episode titles across all feeds
  help           Show this reference (or detail on one command)
{'─'*W}

  Run  podcatcher help <command>  for full syntax and examples.

  Quick examples:
    podcatcher add https://feeds.megaphone.fm/darknetdiaries
    podcatcher add https://feed.syntax.fm/rss --name syntax
    podcatcher list
    podcatcher status syntax
    podcatcher update --download
    podcatcher download syntax --episode 3
    podcatcher mark-played syntax -y
    podcatcher search "linux"
    podcatcher remove syntax
""")


# ─── Argument Parser ───────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="podcatcher",
        description="Podcatcher — command-line podcast manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  podcatcher add https://feeds.megaphone.fm/darknetdiaries
  podcatcher add https://feed.syntax.fm/rss         --name syntax
  podcatcher list
  podcatcher status darknetdiaries
  podcatcher status darknetdiaries --count 20
  podcatcher update
  podcatcher update --slug syntax
  podcatcher update --slug syntax --download
  podcatcher download syntax
  podcatcher download syntax --episode 3
  podcatcher download syntax --all
  podcatcher download
  podcatcher remove syntax
  podcatcher mark-played darknetdiaries
  podcatcher mark-played darknetdiaries --episode 3
  podcatcher mark-played darknetdiaries --unplayed
  podcatcher search "javascript"
""",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # add
    p_add = sub.add_parser("add", help="Add a new podcast feed by URL")
    p_add.add_argument("url", help="RSS feed URL")
    p_add.add_argument("--name", metavar="SLUG", help="Custom short name (slug) for the feed")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", help="List all subscribed feeds")
    p_list.set_defaults(func=cmd_list)

    # status
    p_status = sub.add_parser("status", help="Show detailed info for a feed")
    p_status.add_argument("slug", help="Feed slug (from 'list')")
    p_status.add_argument("--count", type=int, default=10, metavar="N",
                          help="Number of recent episodes to show (default: 10)")
    p_status.set_defaults(func=cmd_status)

    # update
    p_update = sub.add_parser("update", help="Refresh feeds (all, or one by slug)")
    p_update.add_argument("--slug", metavar="SLUG",
                          help="Update only this feed (omit to update all)")
    p_update.add_argument("--download", action="store_true",
                          help="Download any newly discovered episodes after updating")
    p_update.set_defaults(func=cmd_update)

    # remove
    p_remove = sub.add_parser("remove", help="Remove a feed from the list")
    p_remove.add_argument("slug", help="Feed slug")
    p_remove.add_argument("-y", "--yes", action="store_true",
                          help="Skip confirmation prompt")
    p_remove.set_defaults(func=cmd_remove)

    # search
    p_search = sub.add_parser("search", help="Search episode titles across all feeds")
    p_search.add_argument("query", help="Search term")
    p_search.add_argument("--limit", type=int, default=10, metavar="N",
                          help="Max results per feed (default: 10)")
    p_search.set_defaults(func=cmd_search)

    # mark-played
    p_mark = sub.add_parser("mark-played", help="Mark episodes as played (or unplayed)")
    p_mark.add_argument("slug", help="Feed slug")
    p_mark.add_argument("--episode", type=int, metavar="N",
                        help="Mark only episode N (number as shown in 'status'); omit for all")
    p_mark.add_argument("--unplayed", action="store_true",
                        help="Mark as unplayed instead of played")
    p_mark.add_argument("-y", "--yes", action="store_true",
                        help="Skip confirmation prompt when marking all episodes")
    p_mark.set_defaults(func=cmd_mark_played)

    # download
    p_dl = sub.add_parser("download", help="Download episodes (new by default)")
    p_dl.add_argument("slug", nargs="?", metavar="SLUG",
                      help="Feed slug (omit to download from all feeds)")
    p_dl.add_argument("--episode", type=int, metavar="N",
                      help="Download only episode N (requires a slug)")
    p_dl.add_argument("--all", action="store_true",
                      help="Download all episodes not yet on disk")
    p_dl.set_defaults(func=cmd_download)

    # help
    p_help = sub.add_parser("help", help="Show command reference (or detail for one command)")
    p_help.add_argument("topic", nargs="?", metavar="COMMAND",
                        help="Command to show detailed help for (omit for full overview)")
    p_help.set_defaults(func=cmd_help)

    return parser


# ─── Entry Point ───────────────────────────────────────────────────────────────

def main():
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
