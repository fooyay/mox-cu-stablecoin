import pytest
from eth.codecs.abi.exceptions import EncodeError
from src import dsc_engine


def test_reverts_if_token_lengths_are_different(
    dsc, wbtc, weth, btc_usd_price_feed, eth_usd_price_feed
):
    with pytest.raises(EncodeError):
        dsc_engine.deploy(
            [wbtc, weth, weth], [btc_usd_price_feed, eth_usd_price_feed], dsc
        )
