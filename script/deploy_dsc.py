from src import decentralized_stable_coin as dsc
from moccasin.boa_tools import VyperContract

def deploy_dsc() -> VyperContract:
    return dsc.deploy()

def moccasin_main() -> VyperContract:
    return deploy_dsc()