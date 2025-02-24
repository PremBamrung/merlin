"""YouTube integration package for video processing and summarization."""

from merlin.integration.youtube.service import YouTubeService

# For backwards compatibility, expose the service class as YouTube
YouTube = YouTubeService

__all__ = ["YouTube", "YouTubeService"]
