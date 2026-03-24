from hypothesis.stateful import RuleBasedStateMachine, initialize, rule, invariant
from hypothesis import strategies as st
from hypothesis import assume, settings, Phase
from script.deploy_dsc import deploy_dsc
from script.deploy_dsc_engine import deploy_dsc_engine
from moccasin.config import get_active_network
from eth.constants import ZERO_ADDRESS
from boa.util.abi import Address
import boa
from boa.test.strategies import strategy
from eth_utils import to_wei
from boa import BoaError
from src.mocks import MockV3Aggregator  # ty: ignore[unresolved-import]


USERS_SIZE = 10
MAX_DEPOSIT_SIZE = to_wei(1000, "ether")


class StablecoinFuzzer(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()

    @initialize()
    def setup(self):
        self.dsc = deploy_dsc()
        self.dsc_engine = deploy_dsc_engine(self.dsc)

        active_network = get_active_network()
        self.wbtc = active_network.manifest_named("wbtc")
        self.weth = active_network.manifest_named("weth")
        self.btc_usd_price_feed = active_network.manifest_named("btc_usd_price_feed")
        self.eth_usd_price_feed = active_network.manifest_named("eth_usd_price_feed")

        # This convoluted syntax is because we want to prevent the extremely rare
        # case where we generate the zero address as a user. There's probably a clearer
        # way to generate non-zero addresses.
        self.users = [Address("0x" + ZERO_ADDRESS.hex())]
        while Address("0x" + ZERO_ADDRESS.hex()) in self.users:
            self.users = [boa.env.generate_address() for _ in range(USERS_SIZE)]

        # Create a dedicated liquidator with significant DSC reserves
        self.liquidator = boa.env.generate_address()
        self._setup_liquidator()

    @rule(
        collateral_seed=st.integers(min_value=0, max_value=1),
        user_seed=st.integers(min_value=0, max_value=USERS_SIZE - 1),
        amount=strategy("uint256", min_value=1, max_value=MAX_DEPOSIT_SIZE),
    )
    def mint_and_deposit(self, collateral_seed, user_seed, amount):
        # 1. select a random collateral
        collateral = self._get_collateral_from_seed(collateral_seed)
        # 2. deposit a random amount
        user = self.users[user_seed]
        print(f"fuzz - Depositing collateral amount: {amount}")
        with boa.env.prank(user):
            collateral.mint_amount(amount)
            collateral.approve(self.dsc_engine.address, amount)
            self.dsc_engine.deposit_collateral(collateral, amount)

    @rule(
        collateral_seed=st.integers(min_value=0, max_value=1),
        user_seed=st.integers(min_value=0, max_value=USERS_SIZE - 1),
        percentage=st.integers(min_value=1, max_value=100),
    )
    def redeem_collateral(self, collateral_seed, user_seed, percentage):
        # 1. select a random collateral
        collateral = self._get_collateral_from_seed(collateral_seed)
        # 2. redeem a random percentage of the user's collateral
        user = self.users[user_seed]
        max_redeemable = self.dsc_engine.get_collateral_balance_of_user(
            user, collateral
        )
        to_redeem = (max_redeemable * percentage) // 100
        assume(to_redeem > 0)  # if the user has no collateral, skip this step
        print(f"fuzz - Redeeming collateral amount: {to_redeem}")

        with boa.env.prank(user):
            self.dsc_engine.redeem_collateral(collateral, to_redeem)

    @rule(
        collateral_seed=st.integers(min_value=0, max_value=1),
        user_seed=st.integers(min_value=0, max_value=USERS_SIZE - 1),
        amount=strategy("uint256", min_value=1, max_value=MAX_DEPOSIT_SIZE),
    )
    def mint_dsc(self, collateral_seed, user_seed, amount):
        user = self.users[user_seed]
        with boa.env.prank(user):
            try:
                self.dsc_engine.mint_dsc(amount)
            except BoaError as e:
                if "DSCEngine: Health factor too low" in str(e.stack_trace[0].vm_error):
                    collateral = self._get_collateral_from_seed(collateral_seed)
                    collateral_to_deposit = self._get_safe_collateral_top_up(
                        user, collateral.address, amount
                    )
                    self.mint_and_deposit(
                        collateral_seed, user_seed, collateral_to_deposit
                    )
                    self.dsc_engine.mint_dsc(amount)

    @rule(
        percentage_new_price=st.floats(min_value=0.8, max_value=1.0),
        collateral_seed=st.integers(min_value=0, max_value=1),
    )
    def update_collateral_price(self, percentage_new_price, collateral_seed):
        collateral = self._get_collateral_from_seed(collateral_seed)
        price_feed = MockV3Aggregator.at(
            self.dsc_engine.token_to_price_feed(collateral.address)
        )
        current_price = price_feed.latestRoundData()[1]
        new_price = int(current_price * percentage_new_price)
        print(f"fuzz - Updating price from {current_price} to {new_price}")
        price_feed.updateAnswer(new_price)

        # Liquidate any positions with bad health factors
        self._liquidate_bad_positions(collateral_seed)

    @rule(
        collateral_seed=st.integers(min_value=0, max_value=1),
        user_seed=st.integers(min_value=0, max_value=USERS_SIZE - 1),
        amount=strategy("uint256", min_value=1, max_value=MAX_DEPOSIT_SIZE),
    )
    def mint_and_update(self, collateral_seed, user_seed, amount):
        self.mint_and_deposit(collateral_seed, user_seed, amount)
        self.update_collateral_price(0.3, collateral_seed)

    # Invariant: protocol must have more value in collateral than total supply
    @invariant()
    def protocol_must_have_more_value_than_total_supply(self):
        total_supply = self.dsc.totalSupply()
        wbtc_deposited = self.wbtc.balanceOf(self.dsc_engine.address)
        weth_deposited = self.weth.balanceOf(self.dsc_engine.address)

        wbtc_value = self.dsc_engine.get_usd_value(self.wbtc.address, wbtc_deposited)
        weth_value = self.dsc_engine.get_usd_value(self.weth.address, weth_deposited)

        assert total_supply == 0 or (wbtc_value + weth_value) > total_supply

    # helper functions

    def _setup_liquidator(self):
        """
        Initialize the liquidator account used to handle liquidations.
        """
        boa.env.set_balance(self.liquidator, to_wei(10, "ether"))

    def _liquidate_bad_positions(self, collateral_seed: int):
        """
        Liquidate all users whose health factor fell below the minimum after price update.
        """
        collateral = self._get_collateral_from_seed(collateral_seed)
        other_collateral = self.weth if collateral_seed == 0 else self.wbtc

        # Check each user for bad health factor
        for user in self.users:
            dsc_minted = self.dsc_engine.user_to_dsc_minted(user)
            # Skip users with no debt
            if dsc_minted == 0:
                continue

            health_factor = self._get_user_health_factor(user)
            min_health_factor = 10**18  # 1.0 in wei (from MIN_HEALTH_FACTOR in engine)

            if health_factor < min_health_factor:
                # This user needs liquidation
                self._liquidate_user(user, collateral, other_collateral, dsc_minted)

    def _get_user_health_factor(self, user: Address) -> int:
        """
        Calculate health factor for a user.
        On-chain calculation: (collateral_value * 50 / 100) / dsc_minted
        """
        liquidation_threshold = 50
        precision = 100
        system_precision = 10**18

        dsc_minted = self.dsc_engine.user_to_dsc_minted(user)
        if dsc_minted == 0:
            return 2**256 - 1  # max uint256 (healthy)

        # Calculate total collateral value
        collateral_value = 0
        collateral_value += self.dsc_engine.get_usd_value(
            self.wbtc.address,
            self.dsc_engine.get_collateral_balance_of_user(user, self.wbtc),
        )
        collateral_value += self.dsc_engine.get_usd_value(
            self.weth.address,
            self.dsc_engine.get_collateral_balance_of_user(user, self.weth),
        )

        collateral_adjusted = (collateral_value * liquidation_threshold) // precision
        health_factor = (collateral_adjusted * system_precision) // dsc_minted
        return health_factor

    def _liquidate_user(
        self, user_to_liquidate: Address, collateral1, collateral2, max_debt: int
    ):
        """
        Liquidate a user by having the liquidator cover their debt.
        """
        print(f"fuzz - Liquidating user {user_to_liquidate} with debt {max_debt}")

        self._fund_liquidator(max_debt)

        # Get the amount of DSC the liquidator has available
        liquidator_dsc = self.dsc.balanceOf(self.liquidator)
        debt_to_cover = min(max_debt, liquidator_dsc)

        if debt_to_cover == 0:
            print("fuzz - Liquidator has no DSC to cover debt")
            return

        with boa.env.prank(self.liquidator):
            # Try to liquidate with collateral1 first
            collateral_balance_1 = self.dsc_engine.get_collateral_balance_of_user(
                user_to_liquidate, collateral1
            )
            if collateral_balance_1 > 0:
                debt_to_cover = self._get_liquidatable_debt(
                    collateral1.address, collateral_balance_1, max_debt, liquidator_dsc
                )
                if debt_to_cover == 0:
                    return
                try:
                    self.dsc.approve(self.dsc_engine.address, debt_to_cover)
                    self.dsc_engine.liquidate(
                        collateral1.address, user_to_liquidate, debt_to_cover
                    )
                    print(f"fuzz - Successfully liquidated user {user_to_liquidate}")
                    return
                except BoaError as e:
                    print(f"fuzz - Liquidation with collateral1 failed: {e}")

            # Try liquidation with collateral2 if collateral1 had no balance or failed
            collateral_balance_2 = self.dsc_engine.get_collateral_balance_of_user(
                user_to_liquidate, collateral2
            )
            if collateral_balance_2 > 0:
                debt_to_cover = self._get_liquidatable_debt(
                    collateral2.address, collateral_balance_2, max_debt, liquidator_dsc
                )
                if debt_to_cover == 0:
                    return
                try:
                    self.dsc.approve(self.dsc_engine.address, debt_to_cover)
                    self.dsc_engine.liquidate(
                        collateral2.address, user_to_liquidate, debt_to_cover
                    )
                    print(f"fuzz - Successfully liquidated user {user_to_liquidate}")
                except BoaError as e:
                    print(f"fuzz - Liquidation with collateral2 failed: {e}")

    def _fund_liquidator(self, debt_to_cover: int):
        """
        Mint temporary DSC for the liquidator by overcollateralizing with WETH.
        """
        liquidator_dsc = self.dsc.balanceOf(self.liquidator)
        if liquidator_dsc >= debt_to_cover:
            return

        dsc_shortfall = debt_to_cover - liquidator_dsc
        collateral_to_deposit = self._get_safe_collateral_top_up(
            self.liquidator, self.weth.address, dsc_shortfall
        )

        with boa.env.prank(self.liquidator):
            self.weth.mint_amount(collateral_to_deposit)
            self.weth.approve(self.dsc_engine.address, collateral_to_deposit)
            self.dsc_engine.deposit_collateral(self.weth, collateral_to_deposit)
            self.dsc_engine.mint_dsc(dsc_shortfall)

    def _get_safe_collateral_top_up(
        self, user: Address, collateral_address: Address, usd_amount: int
    ):
        """
        Calculate extra collateral needed to keep a user's post-mint position safe.
        """
        target_total_dsc = self.dsc_engine.user_to_dsc_minted(user) + usd_amount
        target_collateral = self.dsc_engine.get_token_amount_from_usd_value(
            collateral_address, target_total_dsc * 3
        )
        target_collateral += 1
        current_collateral = self.dsc_engine.get_collateral_balance_of_user(
            user, collateral_address
        )

        if current_collateral >= target_collateral:
            return 1
        return target_collateral - current_collateral

    def _get_liquidatable_debt(
        self,
        collateral_address: Address,
        collateral_balance: int,
        max_debt: int,
        liquidator_dsc: int,
    ):
        """
        Cap liquidation debt to what the target collateral can pay out with the bonus.
        """
        collateral_value = self.dsc_engine.get_usd_value(
            collateral_address, collateral_balance
        )
        max_collateral_backed_debt = (collateral_value * 100) // 110
        return min(max_debt, liquidator_dsc, max_collateral_backed_debt)

    def _get_collateral_from_seed(self, seed):
        if seed == 0:
            return self.wbtc
        return self.weth


stablecoin_fuzzer = StablecoinFuzzer.TestCase
stablecoin_fuzzer.settings = settings(
    max_examples=40,
    stateful_step_count=20,
    phases=(Phase.generate,),
    database=None,
)
