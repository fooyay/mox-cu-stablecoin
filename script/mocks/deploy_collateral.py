from src.mocks import mock_token
from moccasin.boa_tools import VyperContract


def deploy_collateral() -> VyperContract:
    print("Deploying token...")
    return mock_token.deploy()


def moccasin_main() -> VyperContract:
    return deploy_collateral()
