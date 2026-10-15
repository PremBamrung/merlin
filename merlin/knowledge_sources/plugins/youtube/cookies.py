"""Optional YouTube cookies (settings.youtube_cookies_file).

A Netscape-format cookies.txt exported from a browser signed in to YouTube.
Requests that carry it look like a normal signed-in viewer, which often gets
past YouTube's transcript-endpoint blocks and download refusals. Both
youtube-transcript-api and yt-dlp use it. Unset or missing ⇒ no cookies.
"""

from http.cookiejar import LoadError, MozillaCookieJar
import os
import shutil
import tempfile

import requests

from merlin.config import settings
from merlin.core.logging import logger


def cookie_file() -> str | None:
    """The configured cookies file, or None when unset or not readable."""
    path = settings.youtube_cookies_file.strip()
    if not path:
        return None
    if not os.path.isfile(path):
        logger.warning(f"YOUTUBE_COOKIES_FILE not found: {path} — continuing without")
        return None
    return path


def transcript_http_client() -> requests.Session | None:
    """A requests session carrying the cookies, for YouTubeTranscriptApi."""
    path = cookie_file()
    if not path:
        return None
    jar = MozillaCookieJar(path)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except (LoadError, OSError) as e:
        logger.warning(
            f"Could not load YOUTUBE_COOKIES_FILE ({e}) — continuing without"
        )
        return None
    session = requests.Session()
    session.cookies.update(jar)  # keep requests' own jar (and its API)
    return session


def ytdlp_cookie_copy(out_dir: str) -> str | None:
    """A private copy of the cookies file for one yt-dlp run.

    yt-dlp writes refreshed cookies back to `cookiefile` on exit; a copy keeps
    the user's file untouched (and works when it's mounted read-only).
    """
    path = cookie_file()
    if not path:
        return None
    fd, copy = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt", dir=out_dir)
    os.close(fd)
    shutil.copyfile(path, copy)
    return copy
