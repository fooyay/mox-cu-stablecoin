from hypothesis.stateful import RuleBasedStateMachine, initialize, rule, invariant
from hypothesis import strategies as st
from hypothesis import assume, settings
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
                    amount_to_give = self.dsc_engine.get_token_amount_from_usd_value(
                        collateral, amount
                    )
                    if amount_to_give == 0:
                        amount_to_give = 1
                    amount_to_give *= 2  # give them more than they need to be safe
                    self.mint_and_deposit(collateral_seed, user_seed, amount_to_give)
                    self.dsc_engine.mint_dsc(amount_to_give)

    @rule(
        percentage_new_price=st.floats(min_value=0.2, max_value=1.15),
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

    def _get_collateral_from_seed(self, seed):
        if seed == 0:
            return self.wbtc
        return self.weth


stablecoin_fuzzer = StablecoinFuzzer.TestCase
stablecoin_fuzzer.settings = settings(max_examples=64, stateful_step_count=64)
