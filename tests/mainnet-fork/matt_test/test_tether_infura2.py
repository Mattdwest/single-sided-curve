import pytest

from brownie import Wei, accounts, Contract, config
from brownie import StrategyUSDT3Pool


@pytest.mark.require_network("mainnet-fork")
def test_tether_strategy_infura(pm, chain):
    tether_liquidity = accounts.at(
        "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7", force=True
    )  # using DAI instead of tether. curve pool (lots of dai)

    rewards = accounts[2]
    gov = accounts[3]
    guardian = accounts[4]
    bob = accounts[5]
    alice = accounts[6]
    strategist = accounts[7]

    tether = Contract.from_explorer(
        "0x6b175474e89094c44da98b954eedeac495271d0f", owner=gov
    )  # DAI "Tether" token
    tether.approve(tether_liquidity, Wei("1000000 ether"), {"from": tether_liquidity})
    tether.transferFrom(
        tether_liquidity, gov, Wei("10000 ether"), {"from": tether_liquidity}
    )

    # declaring yUSDT3 as the vault
    Vault = pm(config["dependencies"][0]).Vault
    yUSDT3 = gov.deploy(Vault, tether, gov, rewards, "", "")

    threePool = Contract.from_explorer(
        "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7", owner=gov
    )  # crv3 pool (threePool)
    crv3 = Contract.from_explorer(
        "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490", owner=gov
    )  # crv3 token (threePool)
    yCRV3 = Contract.from_explorer(
        "0x9cA85572E6A3EbF24dEDd195623F188735A5179f", owner=gov
    )  # crv3 vault (threePool)

    strategy = guardian.deploy(
        StrategyUSDT3Pool, yUSDT3, tether, threePool, yCRV3, crv3
    )
    strategy.setStrategist(strategist)

    # adding strategy to the vault
    yUSDT3.addStrategy(strategy, Wei("100000 ether"), 0, 50, {"from": gov})

    # folks need weth for the contract
    tether.approve(gov, Wei("10000 ether"), {"from": gov})
    tether.transferFrom(gov, bob, Wei("100 ether"), {"from": gov})
    tether.transferFrom(gov, alice, Wei("900 ether"), {"from": gov})
    tether.approve(yUSDT3, Wei("1000 ether"), {"from": bob})
    tether.approve(yUSDT3, Wei("1000 ether"), {"from": alice})
    # crv3.approve(yCRV3, Wei("1000000000 ether"), {"from": strategy})

    yUSDT3.deposit(Wei("100 ether"), {"from": bob})
    yUSDT3.deposit(Wei("900 ether"), {"from": alice})
    # strategy.harvest()

    # rHegic.approve(gov, Wei("1000 ether"), {"from": gov})

    # TODO: Instead of sending rhegic to the strategy directly,
    # we should push the clock forward to grab rhegic from Hegic protocol
    # rHegic.transferFrom(gov, strategy, Wei("100 ether"), {"from": gov})

    # strategy.harvest({"from": gov})

    assert 1 == 2

    assert tether.balanceOf(strategy) == 0
    assert yUSDT3.balanceOf(strategy) == 0
    assert yCRV3.balanceOf(strategy) > 0

    yCRV3.transferFrom(gov, strategy, Wei("1000 ether"), {"from": gov})
    strategy.harvest({"from": gov})

    # We should have made profit
    assert yUSDT3.pricePerShare() / 1e18 > 1

    assert 1 == 2
