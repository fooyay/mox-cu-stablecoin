import pytest
from moccasin.config import get_active_network
from script.deploy_dsc_engine import deploy_dsc_engine


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


# function scoped fixtures
@pytest.fixture
def dsc(active_network):
    return active_network.manifest_named("decentralized_stable_coin")


@pytest.fixture
def dsc_engine(dsc, wbtc, weth, btc_usd_price_feed, eth_usd_price_feed):
    return deploy_dsc_engine(dsc, wbtc, weth, btc_usd_price_feed, eth_usd_price_feed)
