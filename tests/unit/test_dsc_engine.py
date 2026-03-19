import prompt_toolkit
from IPython.testing.decorators import f
import pytest
import boa
from eth.codecs.abi.exceptions import EncodeError
from eth_utils import to_wei
from src import dsc_engine
from tests.conftest import COLLATERAL_AMOUNT

UNSUPPORTED_TOKEN: str = "0x0000000000000000000000000000000000000000"

# With COLLATERAL_AMOUNT (10 WETH) at $2,000/ETH => $20,000 collateral.
# At 50% liquidation threshold => max mintable DSC is $10,000.
MINT_AMOUNT: int = to_wei(100, "ether")  # $100 DSC, well below the $10,000 limit
OVER_THRESHOLD_MINT_AMOUNT: int = to_wei(
    10_001, "ether"
)  # $10,001 DSC, just above the $10,000 limit


def test_reverts_if_token_lengths_are_different(
    dsc, wbtc, weth, btc_usd_price_feed, eth_usd_price_feed
):
    with pytest.raises(EncodeError):
        dsc_engine.deploy(
            [wbtc, weth, weth], [btc_usd_price_feed, eth_usd_price_feed], dsc
        )


# deposit collateral


def test_reverts_if_collateral_zero(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        with boa.reverts("DSCEngine: Needs more than zero collateral"):
            dsc_engine.deposit_collateral(weth, 0)


def test_reverts_if_token_not_allowed(some_user, dsc_engine):
    with boa.env.prank(some_user):
        with boa.reverts("DSCEngine: Token not supported"):
            dsc_engine.deposit_collateral(UNSUPPORTED_TOKEN, 1)


def test_good_deposit_does_not_revert(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_collateral(weth, COLLATERAL_AMOUNT)


def test_CollateralDeposited_event_emitted(some_user, weth, dsc_engine):
    # event_signature = "CollateralDeposited(address,address,uint256)"
    # topic0 = boa.env.keccak(event_signature.encode()).hex()
    # topic0 = dsc_engine.compiler_data.abi_dict["CollateralDeposited"].topic_id
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_collateral(weth, COLLATERAL_AMOUNT)

        # logs = [
        #     log
        #     for log in dsc_engine.get_logs()
        #     if type(log).__name__ == "CollateralDeposited"
        # ]
        logs = dsc_engine.get_logs()
        collateral_logs = [
            log
            for log in logs
            # if log.event_type.name == "CollateralDeposited"
            if type(log).__name__ == "CollateralDeposited"
        ]
        print(collateral_logs)
        assert len(collateral_logs) == 1
        event = collateral_logs[0]
        assert event.user == some_user
        assert event.token == weth.address
        assert event.amount == COLLATERAL_AMOUNT


# deposit_and_mint


def test_deposit_and_mint_reverts_if_collateral_zero(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        with boa.reverts("DSCEngine: Needs more than zero collateral"):
            dsc_engine.deposit_and_mint(weth, 0, MINT_AMOUNT)


def test_deposit_and_mint_reverts_if_dsc_amount_zero(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        with boa.reverts("DSCEngine: Need to mint more than 0"):
            dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, 0)


def test_deposit_and_mint_reverts_if_token_not_allowed(some_user, dsc_engine):
    with boa.env.prank(some_user):
        with boa.reverts("DSCEngine: Token not supported"):
            dsc_engine.deposit_and_mint(UNSUPPORTED_TOKEN, COLLATERAL_AMOUNT, MINT_AMOUNT)


def test_deposit_and_mint_reverts_if_health_factor_too_low(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        with boa.reverts("DSCEngine: Health factor too low"):
            dsc_engine.deposit_and_mint(
                weth, COLLATERAL_AMOUNT, OVER_THRESHOLD_MINT_AMOUNT
            )


def test_deposit_and_mint_does_not_revert(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)


def test_deposit_and_mint_updates_collateral_state(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)

    assert (
        dsc_engine.user_to_token_to_amount_deposited(some_user, weth)
        == COLLATERAL_AMOUNT
    )


def test_deposit_and_mint_updates_dsc_minted_state(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)

    assert dsc_engine.user_to_dsc_minted(some_user) == MINT_AMOUNT


def test_deposit_and_mint_transfers_dsc_to_user(some_user, weth, dsc, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)

    assert dsc.balanceOf(some_user) == MINT_AMOUNT
