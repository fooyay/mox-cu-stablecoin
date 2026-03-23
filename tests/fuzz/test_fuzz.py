from hypothesis.stateful import RuleBasedStateMachine, initialize, rule
from script.deploy_dsc import deploy_dsc
from script.deploy_dsc_engine import deploy_dsc_engine
from moccasin.config import get_active_network
from eth.constants import ZERO_ADDRESS
from boa.util.abi import Address
import boa


USERS_SIZE = 10


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

    @rule()
    def pass_me(self):
        pass


stablecoin_fuzzer = StablecoinFuzzer.TestCase
