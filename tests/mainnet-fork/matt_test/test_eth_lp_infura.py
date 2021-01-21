import pytest

from brownie import Wei, accounts, Contract, config
from brownie import StrategyEthHegicLP


@pytest.mark.require_network("mainnet-fork")
def test_rhegic_strategy_infura(pm, chain):
    # probably not needed
    rhegic_liquidity = accounts.at(
        "0x8ac7de95ff8d0ee72e0b54f781ab2e18f27108fb", force=True
    )

    # weth needed to test strategy
    weth_liquidity = accounts.at(
        "0x2f0b23f53734252bda2277357e97e1517d6b042a", force=True
    )  # Maker vault (~2.6mil)

    rewards = accounts[2]
    gov = accounts[3]
    guardian = accounts[4]
    bob = accounts[5]
    alice = accounts[6]
    strategist = accounts[7]

    rHegic = Contract.from_explorer(
        "0x47C0aD2aE6c0Ed4bcf7bc5b380D7205E89436e84", owner=gov
    )
    rHegic.approve(rhegic_liquidity, Wei("1000000 ether"), {"from": rhegic_liquidity})
    rHegic.transferFrom(
        rhegic_liquidity, gov, Wei("888000 ether"), {"from": rhegic_liquidity}
    )

    # vault deals with weth, so addresses need it.
    weth = Contract.from_explorer(
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", owner=gov
    )  # weth token
    weth.approve(weth_liquidity, Wei("100 ether"), {"from": weth_liquidity})
    weth.transferFrom(weth_liquidity, gov, Wei("88 ether"), {"from": weth_liquidity})

    # declaring yEthLP as the vault
    Vault = pm(config["dependencies"][0]).Vault
    yEthLP = gov.deploy(Vault, weth, gov, rewards, "", "")

    ethPool = Contract.from_explorer(
        "0x878F15ffC8b894A1BA7647c7176E4C01f74e140b", owner=gov
    )  # ETH LP pool (writeETH)
    ethPoolStaking = Contract.from_explorer(
        "0x9b18975e64763bDA591618cdF02D2f14a9875981", owner=gov
    )  # ETH LP pool staking for rHegic
    uni = Contract.from_explorer(
        "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", owner=gov
    )  # UNI router v2

    strategy = guardian.deploy(
        StrategyEthHegicLP, weth, yEthLP, rHegic, ethPoolStaking, ethPool, uni
    )
    strategy.setStrategist(strategist)

    # adding strategy to the vault
    yEthLP.addStrategy(strategy, Wei("88 ether"), 0, 50, {"from": gov})

    # folks need weth for the contract
    weth.approve(gov, Wei("100 ether"), {"from": gov})
    weth.transferFrom(gov, bob, Wei("10 ether"), {"from": gov})
    weth.transferFrom(gov, alice, Wei("78 ether"), {"from": gov})
    weth.approve(yEthLP, Wei("100 ether"), {"from": bob})
    weth.approve(yEthLP, Wei("100 ether"), {"from": alice})

    yEthLP.deposit(Wei("10 ether"), {"from": bob})
    yEthLP.deposit(Wei("78 ether"), {"from": alice})
    strategy.harvest()

    rHegic.approve(gov, Wei("1000 ether"), {"from": gov})

    # TODO: Instead of sending rhegic to the strategy directly,
    # we should push the clock forward to grab rhegic from Hegic protocol
    rHegic.transferFrom(gov, strategy, Wei("100 ether"), {"from": gov})

    strategy.harvest({"from": gov})

    assert rHegic.balanceOf(strategy) == 0
    assert ethPool.balanceOf(strategy) == 0
    assert ethPoolStaking.balanceOf(strategy) > 0

    # We should have made profit
    assert yEthLP.pricePerShare() / 1e18 > 1
