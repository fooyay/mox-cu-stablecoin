#!/usr/bin/env python3
"""Quick test to verify liquidation works"""

from script.deploy_dsc import deploy_dsc
from script.deploy_dsc_engine import deploy_dsc_engine
from moccasin.config import get_active_network
import boa
from eth_utils import to_wei
from src.mocks import MockV3Aggregator  # ty: ignore[unresolved-import]


def test_liquidation():
    """Test that liquidation works when price drops"""
    dsc = deploy_dsc()
    dsc_engine = deploy_dsc_engine(dsc)

    active_network = get_active_network()
    wbtc = active_network.manifest_named("wbtc")
    weth = active_network.manifest_named("weth")
    btc_usd_price_feed = active_network.manifest_named("btc_usd_price_feed")
    eth_usd_price_feed = active_network.manifest_named("eth_usd_price_feed")

    # Setup: User deposits collateral and mints DSC
    user = boa.env.generate_address()
    liquidator = boa.env.generate_address()

    with boa.env.prank(user):
        # Deposit collateral
        weth.mint_amount(to_wei(10, "ether"))
        weth.approve(dsc_engine.address, to_wei(10, "ether"))
        dsc_engine.deposit_collateral(weth, to_wei(10, "ether"))

        # Mint DSC (leaving some health factor)
        dsc_engine.mint_dsc(to_wei(9000, "ether"))

    print(f"User DSC minted: {dsc_engine.user_to_dsc_minted(user)}")

    # Check health factor before price crash
    total_dsc = dsc_engine.user_to_dsc_minted(user)
    total_collateral_value = dsc_engine.get_usd_value(weth, to_wei(10, "ether"))
    print(f"Collateral value before crash: {total_collateral_value}")

    # Crash the price

    eth_feed = MockV3Aggregator.at(eth_usd_price_feed.address)
    eth_feed.updateAnswer(150_000_000_000)  # $1500

    print(
        f"Collateral value after crash: {dsc_engine.get_usd_value(weth, to_wei(10, 'ether'))}"
    )

    # Now liquidate
    dsc.mint(liquidator, to_wei(9000, "ether"))

    with boa.env.prank(liquidator):
        dsc.approve(dsc_engine.address, to_wei(9000, "ether"))
        dsc_engine.liquidate(weth, user, to_wei(9000, "ether"))

    print("Liquidation succeeded!")
    print(f"User remaining DSC minted: {dsc_engine.user_to_dsc_minted(user)}")


if __name__ == "__main__":
    test_liquidation()
