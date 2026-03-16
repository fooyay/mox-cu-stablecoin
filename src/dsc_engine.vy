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
from interfaces import AggregatorV3Interface as i_price_feed
from ethereum.ercs import IERC20

# Constants
ADDITIONAL_FEED_PRECISION: constant(uint256) = 10**10  # Chainlink price feeds have 8 decimals, but our system uses 18 decimals, so we need to add 10**10 precision to the price feed values
PRECISION: constant(uint256) = 10**18  # We will use 18 decimals of precision for all calculations in the system
LIQUIDATION_THRESHOLD: constant(uint256) = 50  # If a user's health factor falls below this threshold (e.g. 50%), their position can be liquidated
LIQUIDATION_PRECISION: constant(uint256) = 100 
MIN_HEALTH_FACTOR: constant(uint256) = 1 * 10**18

# State variables
dsc: public(immutable(i_decentralized_stable_coin))
collateral_tokens: public(immutable(address[2]))

# Storage
token_to_price_feed: public(HashMap[address, address])
user_to_token_to_amount_deposited: public(HashMap[address, HashMap[address, uint256]])
user_to_dsc_minted: public(HashMap[address, uint256])

# Events
event CollateralDeposited:
    user: indexed(address)
    token: indexed(address)
    amount: uint256

# external functions

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
def deposit_collateral(token_collateral_address: address, amount_collateral: uint256):
    """
    @param token_collateral_address The address of the collateral token being deposited
    @param amount_collateral The amount of the collateral token being deposited
    @notice Users can call this function to deposit collateral tokens (e.g. WETH, WBTC) into the system. The engine will keep track of how much collateral each user has deposited.
    """
    self._deposit_collateral(token_collateral_address, amount_collateral)

@external
def mint_dsc(amount_dsc_to_mint: uint256):
    """
    @param amount_dsc_to_mint The amount of dsc the user wants to mint
    @notice Users can call this function to mint dsc tokens. The engine will check if the user has enough collateral deposited to mint the requested amount of dsc, and if so, it will call the mint function on the dsc contract to mint the dsc tokens to the user.
    """
    self._mint_dsc(amount_dsc_to_mint)

# internal functions

@internal
def _deposit_collateral(token_collateral_address: address, amount_collateral: uint256):
    """
    @param token_collateral_address The address of the collateral token being deposited
    @param amount_collateral The amount of the collateral token being deposited
    @notice This function contains the logic for depositing collateral. It checks if the
        token is supported and if the amount is greater than zero, then it updates the user's
        deposited collateral amount and transfers the collateral tokens from the user to the engine contract.
    """
    # checks
    assert amount_collateral > 0, "DSCEngine: Needs more than zero collateral"
    assert self.token_to_price_feed[token_collateral_address] != empty(address), "DSCEngine: Token not supported"

    # effects (note: this includes logging)
    self.user_to_token_to_amount_deposited[msg.sender][token_collateral_address] += amount_collateral
    log CollateralDeposited(user=msg.sender, token=token_collateral_address, amount=amount_collateral)

    # interactions
    success: bool = extcall IERC20(token_collateral_address).transferFrom(msg.sender, self, amount_collateral)
    assert success, "DSCEngine: Transfer failed"

@internal
def _mint_dsc(amount_dsc_to_mint: uint256):
    """
    @param amount_dsc_to_mint The amount of dsc the user wants to mint
    @notice This function contains the logic for minting dsc tokens. It checks if the
        user has enough collateral to mint the requested amount of dsc, and if so, it
        updates the user's minted dsc amount and calls the mint function on the dsc contract
        to mint the dsc tokens to the user.
    """
    assert amount_dsc_to_mint > 0, "DSCEngine: Need to mint more than 0"
    self._revert_if_health_factor_too_low(msg.sender) 
    
    self.user_to_dsc_minted[msg.sender] += amount_dsc_to_mint

    extcall dsc.mint(msg.sender, amount_dsc_to_mint)

@internal
def _revert_if_health_factor_too_low(user: address):
    """
    @param user The address of the user whose health factor we want to check
    @notice This function checks the health factor of the user's account and reverts if it is below the minimum threshold.
    """
    health_factor: uint256 = self._health_factor(user)
    assert health_factor >= MIN_HEALTH_FACTOR, "DSCEngine: Health factor too low"


@internal
def _health_factor(user: address) -> uint256:
    """
    @param user The address of the user whose health factor we want to calculate
    @return The health factor of the user's account
    @notice The health factor is a measure of how close the user's account is to being
        undercollateralized. A health factor above 1 means the account is safe, while a
        health factor below 1 means the account is undercollateralized and at risk of liquidation.
    """
    total_dsc_minted: uint256 = 0
    total_collateral_value_in_usd: uint256 = 0
    (total_dsc_minted, total_collateral_value_in_usd) = self._get_account_information(user)
    return self._calculate_health_factor(total_dsc_minted, total_collateral_value_in_usd)

@internal
def _calculate_health_factor(total_dsc_minted: uint256, total_collateral_value_in_usd: uint256) -> uint256:
    """
    @param total_dsc_minted The total amount of dsc the user has minted
    @param total_collateral_value_in_usd The total value of the collateral
        the user has deposited, in USD
    @return The health factor of the user's account, calculated as
        (total collateral value in USD, adjusted for threshold) / (total dsc minted)
    """
    if total_dsc_minted == 0:
        return max_value(uint256)  # If the user hasn't minted any dsc, we can consider their health factor to be infinite (or a very large number) since they have no debt
    collateral_adjusted_for_threshold: uint256 = (total_collateral_value_in_usd * LIQUIDATION_PRECISION) // LIQUIDATION_THRESHOLD
    return (collateral_adjusted_for_threshold * PRECISION) // total_dsc_minted

@internal
def _get_account_information(user: address) -> (uint256, uint256):
    """
    @param user The address of the user whose account information we want to retrieve
    @return A tuple containing:
        - The amount of dsc the user has minted
        - The total value of the collateral the user has deposited (in USD, calculated using the price feeds)
    """
    total_dsc_minted: uint256 = self.user_to_dsc_minted[user]
    collateral_value_in_usd: uint256 = self._get_account_collateral_value(user)

    return (total_dsc_minted, collateral_value_in_usd)

@internal
def _get_account_collateral_value(user: address) -> uint256:
    """
    @param user The address of the user whose collateral value we want to calculate
    @return The total value of the collateral the user has deposited (in USD, calculated using the price feeds)
    """
    total_collateral_value_in_usd: uint256 = 0
    for token: address in collateral_tokens:
        amount: uint256 = self.user_to_token_to_amount_deposited[user][token]
        if amount > 0:
            total_collateral_value_in_usd += self._get_usd_value(token, amount)
    return total_collateral_value_in_usd

@internal
@view
def _get_usd_value(token: address, amount: uint256) -> uint256:
    """
    @param token The address of the token we want to get the USD value of
    @param amount The amount of the token we want to get the USD value of
    @return The USD value of the given amount of the token, calculated using the price feed
    """
    price_feed: i_price_feed = i_price_feed(self.token_to_price_feed[token])
    round_data: (uint80, int256, uint256, uint256, uint80) = staticcall price_feed.latestRoundData()
    price: int256 = round_data[1]
    return ((convert(price, uint256) * ADDITIONAL_FEED_PRECISION) * amount) // PRECISION  # adjusting for decimals and precision
    
