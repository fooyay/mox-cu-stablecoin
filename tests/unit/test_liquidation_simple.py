"""
Simple test to verify liquidation logic works.
"""

from script.deploy_dsc import deploy_dsc
from script.deploy_dsc_engine import deploy_dsc_engine
from moccasin.config import get_active_network
from eth_utils import to_wei
from src.mocks import MockV3Aggregator  # ty: ignore[unresolved-import]
import boa


def test_liquidation_on_price_drop():
    """Test that liquidation is triggered when price drops below threshold."""

    # Deploy contracts
    dsc = deploy_dsc()
    dsc_engine = deploy_dsc_engine(dsc)

    active_network = get_active_network()
    wbtc = active_network.manifest_named("wbtc")
    weth = active_network.manifest_named("weth")
    eth_usd_price_feed = active_network.manifest_named("eth_usd_price_feed")

    # Create user and liquidator
    user = boa.env.generate_address()
    liquidator = boa.env.generate_address()

    # Setup liquidator with collateral and lots of DSC
    initial_eth_amount = to_wei(100, "ether")
    with boa.env.prank(liquidator):
        weth.mint_amount(initial_eth_amount)
        weth.approve(dsc_engine.address, initial_eth_amount)
        dsc_engine.deposit_collateral(weth, initial_eth_amount)
        dsc_engine.mint_dsc(to_wei(10000, "ether"))  # Mint 10000 DSC for liquidations

    # Setup user: 10 WETH at $2000 =>$20,000 collateral
    # Mint 9,000 DSC (health factor ≈ 1.11, healthy)
    user_eth_amount = to_wei(10, "ether")
    user_dsc_amount = to_wei(9000, "ether")

    with boa.env.prank(user):
        weth.mint_amount(user_eth_amount)
        weth.approve(dsc_engine.address, user_eth_amount)
        dsc_engine.deposit_collateral(weth, user_eth_amount)
        dsc_engine.mint_dsc(user_dsc_amount)

    # Check health factor before price drop
    print(f"✓ User position established: {user_dsc_amount / 10**18} DSC minted")

    #  Drop price to $1,500 (from $2,000)
    # At $1,500: adjusted collateral = $7,500, health factor = 7,500 / 9,000 ≈ 0.83
    price_feed = MockV3Aggregator.at(dsc_engine.token_to_price_feed(weth.address))
    current_price = price_feed.latestRoundData()[1]
    new_price = 150_000_000_000  # $1,500 in 8-decimal Chainlink format
    print(
        f"✓ Price dropping from {current_price / 10**8}$ to {new_price / 10**8}$ per ETH"
    )
    price_feed.updateAnswer(new_price)

    # Check that user is now underwater
    dsc_minted = dsc_engine.user_to_dsc_minted(user)
    user_eth_collateral = dsc_engine.get_collateral_balance_of_user(user, weth)
    print(
        f"✓ After price drop - User has {user_eth_collateral / 10**18} ETH of collateral and {dsc_minted / 10**18} DSC debt"
    )

    # Liquidate 4,500 DSC (50% of debt)
    debt_to_cover = dsc_minted // 2
    liquidator_dsc_balance = dsc.balanceOf(liquidator)
    print(
        f"✓ Liquidator has {liquidator_dsc_balance / 10**18} DSC available to cover debt"
    )

    with boa.env.prank(liquidator):
        dsc.approve(dsc_engine.address, debt_to_cover)
        dsc_engine.liquidate(weth.address, user, debt_to_cover)

    # After liquidation, user should have 4,500 DSC remaining
    dsc_after = dsc_engine.user_to_dsc_minted(user)
    expected_dsc = user_dsc_amount - debt_to_cover
    print(
        f"✓ After liquidation - User has {dsc_after / 10**18} DSC remaining (expected {expected_dsc / 10**18})"
    )
    assert dsc_after == expected_dsc, f"Expected {expected_dsc}, got {dsc_after}"

    # Verify invariant: total DSC <= collateral value
    total_supply = dsc.totalSupply()
    weth_in_engine = weth.balanceOf(dsc_engine.address)
    weth_value = dsc_engine.get_usd_value(weth.address, weth_in_engine)
    print(
        f"✓ Invariant check: Total DSC supply {total_supply / 10**18} <= Collateral value ${weth_value / 10**18}"
    )
    assert total_supply <= weth_value, (
        f"Invariant failed: {total_supply} > {weth_value}"
    )

    print("✅ Liquidation test PASSED!")


if __name__ == "__main__":
    test_liquidation_on_price_drop()
