"""
playlist_ingestor.py
--------------------
Self-contained utility for enumerating YouTube playlist and batch-file URLs.

This module extracts the playlist/batch enumeration logic from the old
summarize_yt.py CLI script so it can be wired into the new backend's plugin
system without touching the CLI concerns (argparse, tqdm, file I/O).

Backend integration point
-------------------------
The intended hook is `YouTubePlugin.ingest()` in
`backend/knowledge_sources/plugins/youtube/plugin.py`.

When a playlist URL is submitted to `POST /api/sources/youtube`, the plugin
should:
  1. Call `is_playlist_url(url)` to detect the URL type.
  2. Call `enumerate_playlist_urls(url)` to get the individual video URLs.
  3. Enqueue each video URL as a separate background task via
     `task_queue.enqueue_ingest()`.

Dependencies
------------
  pip install pytube

Usage example
-------------
  from merlin.integration.youtube.playlist_ingestor import (
      is_playlist_url,
      enumerate_playlist_urls,
      enumerate_batch_file_urls,
  )

  # Playlist
  if is_playlist_url(url):
      video_urls = enumerate_playlist_urls(url)
      for video_url in video_urls:
          ...  # enqueue or process

  # Batch file (list of URLs, one per line)
  video_urls = enumerate_batch_file_urls("urls.txt")
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterator


def is_playlist_url(url: str) -> bool:
    """Return True if *url* points to a YouTube playlist rather than a single video.

    A URL is considered a playlist when it contains a ``list=`` query parameter
    (e.g. ``https://www.youtube.com/playlist?list=PLxxx`` or a video URL with
    ``&list=PLxxx`` appended).

    Args:
        url: Raw URL string submitted by the user.

    Returns:
        True for playlist URLs, False for single-video URLs.
    """
    return bool(re.search(r"[?&]list=", url))


def enumerate_playlist_urls(playlist_url: str) -> list[str]:
    """Return the ordered list of video URLs in a YouTube playlist.

    Fetches the playlist metadata via pytube and returns each video's
    canonical ``https://www.youtube.com/watch?v=<id>`` URL.

    Args:
        playlist_url: Full URL of the YouTube playlist
                      (``https://www.youtube.com/playlist?list=PLxxx``).

    Returns:
        List of video URLs in playlist order.  May be empty if the playlist
        is private or pytube cannot access it.

    Raises:
        ImportError: If pytube is not installed.
        Exception:   Propagates pytube / network errors so the caller can
                     decide whether to retry or mark the task as failed.
    """
    from pytube import (
        Playlist,  # local import so the rest of the module loads without pytube
    )

    playlist = Playlist(playlist_url)
    return list(playlist.video_urls)


def enumerate_playlist_urls_lazy(playlist_url: str) -> Iterator[str]:
    """Lazy iterator variant of :func:`enumerate_playlist_urls`.

    Yields each video URL one at a time, which is useful when enqueuing
    tasks incrementally for very large playlists rather than waiting for
    the full list to materialise.

    Args:
        playlist_url: Full URL of the YouTube playlist.

    Yields:
        Individual video URLs in playlist order.
    """
    from pytube import Playlist

    playlist = Playlist(playlist_url)
    yield from playlist.video_urls


def enumerate_batch_file_urls(file_path: str | Path) -> list[str]:
    """Return the list of video URLs from a plain-text batch file.

    Each non-empty, non-comment line is treated as a URL.  Lines starting
    with ``#`` are silently skipped.

    Args:
        file_path: Path to a text file containing one YouTube URL per line.

    Returns:
        Ordered list of URLs with blank lines and comments stripped.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
    """
    path = Path(file_path)
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def playlist_title_slug(playlist_url: str) -> str:
    """Return a filesystem-safe slug derived from a playlist title.

    Useful for naming output directories.  Requires pytube.

    Args:
        playlist_url: Full URL of the YouTube playlist.

    Returns:
        Lowercase, underscore-joined slug from the first few words of the
        playlist title, e.g. ``"machine_learning_crash_course"``.
    """
    from pytube import Playlist

    playlist = Playlist(playlist_url)
    title = re.sub(r"[^a-zA-Z0-9 ]+", " ", playlist.title or "playlist")
    return "_".join(title.split()).lower()
