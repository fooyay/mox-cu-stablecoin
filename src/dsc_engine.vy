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



DSC: public(immutable(i_decentralized_stable_coin))


@deploy
def __init__(
    token_addresses: address[2], 
    price_feed_addresses: address[2],
    dsc_address: address,
):
    """
    @param token_addresses: An array of addresses for the collateral tokens (e.g. WETH, WBTC)
    @param price_feed_addresses: An array of addresses for the price feeds corresponding to the collateral tokens (e.g. Chainlink price feeds for WETH/USD and WBTC/USD)
    @param dsc_address: The address of the DSC contract, which we will use to mint and burn DSC
    """
    DSC = i_decentralized_stable_coin(dsc_address)
