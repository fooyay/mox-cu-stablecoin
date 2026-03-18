import pytest
from moccasin.config import get_active_network


# session scoped fixtures
@pytest.fixture(scope="session")
def active_network():
    return get_active_network()


@pytest.fixture(scope="session")
def weth(active_network):
    return active_network.manifest_named("weth")


@pytest.fixture(scope="session")
def wbtc(active_network):
    return active_network.manifest_named("wbtc")


@pytest.fixture(scope="session")
def btc_usd_price_feed(active_network):
    return active_network.manifest_named("btc_usd_price_feed")


@pytest.fixture(scope="session")
def eth_usd_price_feed(active_network):
    return active_network.manifest_named("eth_usd_price_feed")
