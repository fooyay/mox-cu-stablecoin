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
        with boa.reverts("DSCEngine: Needs more than zero collateral"):
            dsc_engine.deposit_collateral(weth, 0)


def test_reverts_if_token_not_allowed(some_user, dsc_engine):
    bad_token = "0x0000000000000000000000000000000000000000"
    with boa.env.prank(some_user):
        with boa.reverts("DSCEngine: Token not supported"):
            dsc_engine.deposit_collateral(bad_token, 1)
