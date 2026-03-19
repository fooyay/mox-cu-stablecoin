import prompt_toolkit
from IPython.testing.decorators import f
import pytest
import boa
from eth.codecs.abi.exceptions import EncodeError
from eth_account import Account
from eth_utils import to_wei
from src import dsc_engine
from tests.conftest import COLLATERAL_AMOUNT, INITIAL_BALANCE

UNSUPPORTED_TOKEN: str = "0x0000000000000000000000000000000000000000"

# With COLLATERAL_AMOUNT (10 WETH) at $2,000/ETH => $20,000 collateral.
# At 50% liquidation threshold => max mintable DSC is $10,000.
MINT_AMOUNT: int = to_wei(100, "ether")  # $100 DSC, well below the $10,000 limit
OVER_THRESHOLD_MINT_AMOUNT: int = to_wei(
    10_001, "ether"
)  # $10,001 DSC, just above the $10,000 limit

# Liquidation scenario:
#   some_user deposits 10 WETH at $2,000 => $20,000 collateral, threshold => $10,000 max
#   mints $9,000 DSC => health_factor = 10,000/9,000 ≈ 1.11 (healthy)
#   price crashes to $1,500 => adjusted collateral = $7,500
#   health_factor = 7,500/9,000 ≈ 0.83 < 1 (undercollateralized)
LIQUIDATION_MINT_AMOUNT: int = to_wei(9_000, "ether")
CRASHED_ETH_PRICE: int = 150_000_000_000  # $1,500 in Chainlink 8-decimal format


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
            dsc_engine.deposit_and_mint(
                UNSUPPORTED_TOKEN, COLLATERAL_AMOUNT, MINT_AMOUNT
            )


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


# redeem_collateral


def test_redeem_collateral_reverts_if_amount_exceeds_deposited(
    some_user, weth, dsc_engine
):
    # No collateral deposited — underflow causes a revert.
    with boa.env.prank(some_user):
        with boa.reverts():
            dsc_engine.redeem_collateral(weth, COLLATERAL_AMOUNT)


def test_redeem_collateral_reverts_if_health_factor_breaks(some_user, weth, dsc_engine):
    # Deposit collateral, mint DSC, then try to redeem all collateral —
    # health factor would drop to zero, so it must revert.
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)
        with boa.reverts("DSCEngine: Health factor too low"):
            dsc_engine.redeem_collateral(weth, COLLATERAL_AMOUNT)


def test_redeem_collateral_does_not_revert(some_user, weth, dsc_engine):
    # No DSC minted, so redeeming all collateral keeps health factor at max.
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_collateral(weth, COLLATERAL_AMOUNT)
        dsc_engine.redeem_collateral(weth, COLLATERAL_AMOUNT)


def test_redeem_collateral_updates_collateral_state(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_collateral(weth, COLLATERAL_AMOUNT)
        dsc_engine.redeem_collateral(weth, COLLATERAL_AMOUNT)

    assert dsc_engine.user_to_token_to_amount_deposited(some_user, weth) == 0


def test_redeem_collateral_returns_tokens_to_user(some_user, weth, dsc_engine):
    balance_before = weth.balanceOf(some_user)
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_collateral(weth, COLLATERAL_AMOUNT)
        dsc_engine.redeem_collateral(weth, COLLATERAL_AMOUNT)

    assert weth.balanceOf(some_user) == balance_before


def test_redeem_collateral_emits_event(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_collateral(weth, COLLATERAL_AMOUNT)
        dsc_engine.redeem_collateral(weth, COLLATERAL_AMOUNT)

        logs = [
            log
            for log in dsc_engine.get_logs()
            if type(log).__name__ == "CollateralRedeemed"
        ]
        assert len(logs) == 1
        event = logs[0]
        assert event.token == weth.address
        assert event.amount == COLLATERAL_AMOUNT
        assert (
            event._3 == some_user
        )  # _from field (renamed by namedtuple due to leading underscore)
        assert (
            event._4 == some_user
        )  # _to field (renamed by namedtuple due to leading underscore)


# redeem_for_dsc


def test_redeem_for_dsc_does_not_revert(some_user, weth, dsc, dsc_engine):
    # Setup: deposit collateral and mint DSC.
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)
        # Grant the engine allowance to burn the user's DSC.
        dsc.approve(dsc_engine, MINT_AMOUNT)
        dsc_engine.redeem_for_dsc(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)

    assert dsc_engine.user_to_dsc_minted(some_user) == 0
    assert dsc_engine.user_to_token_to_amount_deposited(some_user, weth) == 0
    assert dsc.balanceOf(some_user) == 0
    assert weth.balanceOf(some_user) == COLLATERAL_AMOUNT


# mint_dsc


def test_mint_dsc_reverts_if_health_factor_too_low(some_user, weth, dsc_engine):
    # No collateral deposited, so minting any DSC breaks the health factor.
    with boa.env.prank(some_user):
        with boa.reverts("DSCEngine: Health factor too low"):
            dsc_engine.mint_dsc(MINT_AMOUNT)


def test_mint_dsc_does_not_revert(some_user, weth, dsc, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_collateral(weth, COLLATERAL_AMOUNT)
        dsc_engine.mint_dsc(MINT_AMOUNT)

    assert dsc_engine.user_to_dsc_minted(some_user) == MINT_AMOUNT
    assert dsc.balanceOf(some_user) == MINT_AMOUNT


# burn_dsc


def test_burn_dsc_reverts_if_no_dsc_to_burn(some_user, dsc_engine):
    # No DSC minted, so burning any amount causes an underflow revert.
    with boa.env.prank(some_user):
        with boa.reverts():
            dsc_engine.burn_dsc(MINT_AMOUNT)


def test_burn_dsc_does_not_revert(some_user, weth, dsc, dsc_engine):
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, MINT_AMOUNT)
        dsc.approve(dsc_engine, MINT_AMOUNT)
        dsc_engine.burn_dsc(MINT_AMOUNT)

    assert dsc_engine.user_to_dsc_minted(some_user) == 0
    assert dsc.balanceOf(some_user) == 0


# liquidate


def test_liquidate_reverts_if_debt_to_cover_zero(some_user, weth, dsc_engine):
    with boa.env.prank(some_user):
        with boa.reverts("DSCEngine: No debt to cover"):
            dsc_engine.liquidate(weth, some_user, 0)


def test_liquidate_reverts_if_position_is_healthy(some_user, weth, dsc_engine):
    # some_user has no DSC minted so health factor is max — not liquidatable.
    with boa.env.prank(some_user):
        with boa.reverts("DSCEngine: Can't liquidate a healthy position"):
            dsc_engine.liquidate(weth, some_user, MINT_AMOUNT)


def test_liquidate_clears_undercollateralized_position(
    some_user, weth, wbtc, eth_usd_price_feed, dsc, dsc_engine
):
    # bad user: deposit WETH and mint near-limit DSC.
    with boa.env.prank(some_user):
        weth.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(weth, COLLATERAL_AMOUNT, LIQUIDATION_MINT_AMOUNT)

    # liquidator: deposit WBTC (price unaffected by ETH crash) and mint matching DSC.
    liquidator = Account.create(99).address
    boa.env.set_balance(liquidator, INITIAL_BALANCE)
    with boa.env.prank(liquidator):
        wbtc.mock_mint()
        wbtc.approve(dsc_engine, COLLATERAL_AMOUNT)
        dsc_engine.deposit_and_mint(wbtc, COLLATERAL_AMOUNT, LIQUIDATION_MINT_AMOUNT)

    # Crash ETH price inside an anchor so the change doesn't leak to other tests.
    with boa.env.anchor():
        eth_usd_price_feed.updateAnswer(CRASHED_ETH_PRICE)

        with boa.env.prank(liquidator):
            dsc.approve(dsc_engine, LIQUIDATION_MINT_AMOUNT)
            dsc_engine.liquidate(weth, some_user, LIQUIDATION_MINT_AMOUNT)

        # Bad user's debt and collateral should be cleared.
        assert dsc_engine.user_to_dsc_minted(some_user) == 0
        assert (
            dsc_engine.user_to_token_to_amount_deposited(some_user, weth)
            < COLLATERAL_AMOUNT
        )
        # Liquidator received some_user's WETH (collateral + 10% bonus).
        assert weth.balanceOf(liquidator) > 0
