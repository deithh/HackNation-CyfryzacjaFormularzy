from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage
from testcontainers.core.network import Network
from testcontainers.core.wait_strategies import HttpWaitStrategy, PortWaitStrategy

REPO_ROOT = Path(__file__).resolve().parents[3]
TIKA_PORT = 8081
UNOSERVER_PORT = 2003


@pytest.fixture(scope="session")
def network():
    with Network() as net:
        yield net


@pytest.fixture(scope="session")
def tika_url(network):
    with DockerImage(path=str(REPO_ROOT / "tika"), tag="form-digitizer-tika:test") as image:
        container = (
            DockerContainer(str(image.tag))
            .with_command(f"-p {TIKA_PORT} -c /tika-config.xml")
            .with_exposed_ports(TIKA_PORT)
            .waiting_for(HttpWaitStrategy(TIKA_PORT, "/tika").for_status_code(200).with_startup_timeout(180))
        )
        with container:
            yield f"http://{container.get_container_host_ip()}:{container.get_exposed_port(TIKA_PORT)}"


@pytest.fixture(scope="session")
def unoserver_url(network):
    with DockerImage(path=str(REPO_ROOT / "unoserver"), tag="form-digitizer-unoserver:test") as image:
        container = (
            DockerContainer(str(image.tag))
            .with_exposed_ports(UNOSERVER_PORT)
            .waiting_for(PortWaitStrategy(UNOSERVER_PORT).with_startup_timeout(180))
        )
        with container:
            yield f"http://{container.get_container_host_ip()}:{container.get_exposed_port(UNOSERVER_PORT)}"


@pytest.fixture(scope="session")
def services(tika_url, unoserver_url):
    from app.config import config

    patch = pytest.MonkeyPatch()
    patch.setattr(config, "extractor_url", tika_url)
    patch.setattr(config, "converter_url", unoserver_url)
    yield
    patch.undo()


@pytest.fixture
def client(services):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
