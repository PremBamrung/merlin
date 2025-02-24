import pytest
from app.main import app
from app.models.database import Base, Video, engine, get_db
from httpx import AsyncClient
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before tests and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Get database session."""
    try:
        db = next(get_db())
        yield db
    finally:
        db.close()


@pytest.fixture
async def client():
    """Get async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_process_video(client: AsyncClient, db: Session):
    """Test video processing endpoint."""
    # Test data
    test_url = "https://www.youtube.com/watch?v=test_video_id"

    # Make request
    response = await client.post(
        "/api/v1/youtube/videos/process",
        json={
            "url": test_url,
            "language": "english",
            "summary_length": "short",
            "tags": "test,integration",
        },
    )

    # Assert response
    assert response.status_code == 200
    data = response.json()
    assert "video" in data
    video = data["video"]
    assert video["video_id"] == "test_video_id"

    # Verify database entry
    db_video = db.query(Video).filter(Video.video_id == "test_video_id").first()
    assert db_video is not None
    assert db_video.tags == "test,integration"


@pytest.mark.asyncio
async def test_get_videos(client: AsyncClient, db: Session):
    """Test getting videos endpoint."""
    # Create test video in database
    video = Video(
        video_id="test_id",
        title="Test Video",
        channel="Test Channel",
        summary="Test summary",
        tags="test,video",
    )
    db.add(video)
    db.commit()

    # Test getting all videos
    response = await client.get("/api/v1/youtube/videos")
    assert response.status_code == 200
    videos = response.json()
    assert len(videos) == 1
    assert videos[0]["video_id"] == "test_id"

    # Test search by query
    response = await client.get("/api/v1/youtube/videos?query=Test")
    assert response.status_code == 200
    videos = response.json()
    assert len(videos) == 1

    # Test search by tag
    response = await client.get("/api/v1/youtube/videos?tags=test")
    assert response.status_code == 200
    videos = response.json()
    assert len(videos) == 1

    # Test no results
    response = await client.get("/api/v1/youtube/videos?query=nonexistent")
    assert response.status_code == 200
    videos = response.json()
    assert len(videos) == 0


@pytest.mark.asyncio
async def test_get_video(client: AsyncClient, db: Session):
    """Test getting a specific video endpoint."""
    # Create test video
    video = Video(
        video_id="test_id",
        title="Test Video",
        channel="Test Channel",
        summary="Test summary",
    )
    db.add(video)
    db.commit()

    # Test getting existing video
    response = await client.get("/api/v1/youtube/videos/test_id")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "test_id"

    # Test getting non-existent video
    response = await client.get("/api/v1/youtube/videos/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_video(client: AsyncClient, db: Session):
    """Test updating a video endpoint."""
    # Create test video
    video = Video(
        video_id="test_id",
        title="Test Video",
        channel="Test Channel",
        summary="Test summary",
    )
    db.add(video)
    db.commit()

    # Test updating existing video
    update_data = {"summary": "Updated summary", "tags": "updated,test"}
    response = await client.put("/api/v1/youtube/videos/test_id", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Updated summary"
    assert data["tags"] == "updated,test"

    # Test updating non-existent video
    response = await client.put("/api/v1/youtube/videos/nonexistent", json=update_data)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_video(client: AsyncClient, db: Session):
    """Test deleting a video endpoint."""
    # Create test video
    video = Video(
        video_id="test_id",
        title="Test Video",
        channel="Test Channel",
        summary="Test summary",
    )
    db.add(video)
    db.commit()

    # Test deleting existing video
    response = await client.delete("/api/v1/youtube/videos/test_id")
    assert response.status_code == 200

    # Verify video was deleted
    db_video = db.query(Video).filter(Video.video_id == "test_id").first()
    assert db_video is None

    # Test deleting non-existent video
    response = await client.delete("/api/v1/youtube/videos/nonexistent")
    assert response.status_code == 404
