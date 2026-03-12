# pragma version 0.4.3
"""
@license MIT
@title Decentralized Stable Coin Engine
@author Sean Coates
@notice
    Collateral: Exogenous (WETH, WBTC, etc.)
    Minting (Stability) Mechanism: Decentralized (Algorithmic)
    Value (Relative Stability): Anchored (Pegged to USD)
    Collateral Type: Crypto (ERC-20 Tokens)
"""
from interfaces import i_decentralized_stable_coin
from ethereum.ercs import IERC20


# State variables
dsc: public(immutable(i_decentralized_stable_coin))
collateral_tokens: public(immutable(address[2]))

# Storage
token_to_price_feed: public(HashMap[address, address])
user_to_token_to_amount_deposited: public(HashMap[address, HashMap[address, uint256]])

# Events
event CollateralDeposited:
    user: indexed(address)
    token: indexed(address)
    amount: uint256


@deploy
def __init__(
    token_addresses: address[2], 
    price_feed_addresses: address[2],
    dsc_address: address,
):
    """
    @param token_addresses An array of addresses for the collateral tokens (e.g. WETH, WBTC)
    @param price_feed_addresses An array of addresses for the price feeds corresponding to the collateral tokens (e.g. Chainlink price feeds for WETH/USD and WBTC/USD)
    @param dsc_address The address of the dsc contract, which we will use to mint and burn dsc tokens
    """
    dsc = i_decentralized_stable_coin(dsc_address)
    collateral_tokens = token_addresses
    self.token_to_price_feed[token_addresses[0]] = price_feed_addresses[0]
    self.token_to_price_feed[token_addresses[1]] = price_feed_addresses[1]

@external
def deposit_collateral(token: address, amount: uint256):
    """
    @param token The address of the collateral token being deposited
    @param amount The amount of the collateral token being deposited
    @notice Users can call this function to deposit collateral tokens (e.g. WETH, WBTC) into the system. The engine will keep track of how much collateral each user has deposited.
    """
    self._deposit_collateral(token, amount)

@internal
def _deposit_collateral(token_collateral_address: address, amount_collateral: uint256):
    assert amount_collateral > 0, "DSCEngine: Needs more than zero collateral"
    assert self.token_to_price_feed[token_collateral_address] != empty(address), "DSCEngine: Token not supported"

    self.user_to_token_to_amount_deposited[msg.sender][token_collateral_address] += amount_collateral
    log CollateralDeposited(user=msg.sender, token=token_collateral_address, amount=amount_collateral)

    success: bool = extcall IERC20(token_collateral_address).transferFrom(msg.sender, self, amount_collateral)
    assert success, "DSCEngine: Transfer failed"