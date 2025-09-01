# tests/conftest.py
import os
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

from app.main import app
from app.db.mongo import get_db
from app.deps.auth import UsuarioToken, get_usuario_atual

# ID fixo do usuário de teste
TEST_USER_ID = ObjectId("66aabbccddeeff0011223344")

@pytest.fixture(scope="session")
def test_user_id_str():
    return str(TEST_USER_ID)

@pytest.fixture(scope="session", autouse=True)
def _tmp_data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("data_dir")
    os.environ["DATA_DIR"] = str(d)  # força o app a salvar em tmp
    return d

@pytest.fixture(scope="session")
def db_client():
    return AsyncMongoMockClient()

@pytest.fixture(scope="session")
def db(db_client):
    return db_client["testdb"]

@pytest.fixture(autouse=True)
async def override_db_and_auth(db):
    async def _get_db_override():
        return db
    app.dependency_overrides[get_db] = _get_db_override

    async def _get_user_override():
        return UsuarioToken(id=TEST_USER_ID, username="tester")
    app.dependency_overrides[get_usuario_atual] = _get_user_override

    # Mock da task Celery: gerar_audio_google_task.delay
    from app.tasks import audio as audio_tasks
    original_delay = getattr(audio_tasks.gerar_audio_google_task, "delay", None)

    class _DelayMock:
        def __call__(self, pdf_id: str):
            # não dispara nada nos testes; simulamos manualmente
            return None

    audio_tasks.gerar_audio_google_task.delay = _DelayMock()

    yield

    app.dependency_overrides.clear()
    if original_delay is not None:
        audio_tasks.gerar_audio_google_task.delay = original_delay

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def auth_headers():
    # Como get_usuario_atual é sobrescrito, o header é apenas decorativo
    return {"Authorization": "Bearer fake-token-for-tests"}
