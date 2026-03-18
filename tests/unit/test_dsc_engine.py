import pytest
import boa
from eth.codecs.abi.exceptions import EncodeError
from src import dsc_engine
from tests.conftest import COLLATERAL_AMOUNT


def test_reverts_if_token_lengths_are_different(
    dsc, wbtc, weth, btc_usd_price_feed, eth_usd_price_feed
):
    with pytest.raises(EncodeError):
        dsc_engine.deploy(
            [wbtc, weth, weth], [btc_usd_price_feed, eth_usd_price_feed], dsc
        )


def test_reverts_if_collateral_zero(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        with boa.reverts():
            dsc_engine.deposit_collateral(weth, 0)
