# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")

import pytest

from brownie import Wei, accounts, Contract, config
from brownie import StrategyUSDT3Poolv2


@pytest.mark.require_network("mainnet-fork")
def test_operation(pm, chain):
    usdt_liquidity = accounts.at(
        "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7", force=True
    )  # using curve pool (lots of dai)

    crv3_liquidity =  accounts.at(
        "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490", force=True
    )  # yearn treasury (lots of crv3)

    rewards = accounts[2]
    gov = accounts[3]
    guardian = accounts[4]
    bob = accounts[5]
    alice = accounts[6]
    strategist = accounts[7]
    tinytim = accounts[8]

    usdt = Contract("0xdac17f958d2ee523a2206206994597c13d831ec7", owner=gov)  # USDt token

    usdt.approve(usdt_liquidity, Wei("1000000 ether"), {"from": usdt_liquidity})
    usdt.transferFrom(usdt_liquidity, gov, 300000000000, {"from": usdt_liquidity})

    crv3 = Contract(
        "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490", owner=gov
    )  # crv3 token address (threePool)

    crv3.approve(crv3_liquidity, Wei("1000000 ether"), {"from": crv3_liquidity})
    crv3.transferFrom(crv3_liquidity, gov, Wei("100 ether"), {"from": crv3_liquidity})

    # config yvDAI vault.
    Vault = pm(config["dependencies"][0]).Vault
    yUSDT3 = Vault.deploy({"from": gov})
    yUSDT3.initialize(usdt, gov, rewards, "", "")
    yUSDT3.setDepositLimit(Wei("1000000 ether"))

    threePool = Contract(
        "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7", owner=gov
    )  # crv3 pool address (threePool)
    yCRV3 = Contract(
        "0x9cA85572E6A3EbF24dEDd195623F188735A5179f", owner=gov
    )  # crv3 vault (threePool)
    #crv3Strat = Contract(
    #    "0xC59601F0CC49baa266891b7fc63d2D5FE097A79D", owner=gov
    #)  # crv3 strat (threePool)
    #crv3StratOwner = Contract(
    #    "0xd0aC37E3524F295D141d3839d5ed5F26A40b589D", owner=gov
    #)  # crv3 stratOwner (threePool)
    # uni = Contract.from_explorer(
    #  "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", owner=gov
    # )  # UNI router v2

    strategy = guardian.deploy(StrategyUSDT3Poolv2, yUSDT3, usdt, threePool, yCRV3, crv3)
    strategy.setStrategist(strategist)

    yUSDT3.addStrategy(
        strategy, 10_000, 0, 0, {"from": gov}
    )

    usdt.approve(gov, Wei("1000000 ether"), {"from": gov})
    usdt.transferFrom(gov, bob, 1000000000, {"from": gov})
    usdt.transferFrom(gov, alice, 4000000000, {"from": gov})
    usdt.transferFrom(gov, tinytim, 10000000, {"from":gov})
    usdt.approve(yUSDT3, Wei("1000000 ether"), {"from": bob})
    usdt.approve(yUSDT3, Wei("1000000 ether"), {"from": alice})
    usdt.approve(yUSDT3, Wei("1000000 ether"), {"from": tinytim})
    crv3.approve(gov, Wei("1000000 ether"), {"from": gov})
    yUSDT3.approve(gov, Wei("1000000 ether"), {"from": gov})
    crv3.approve(yCRV3, Wei("1000000 ether"), {"from": gov})
    usdt.approve(threePool, Wei("1000000 ether"), {"from": gov})

    usdt.approve(threePool, Wei("1000000 ether"), {"from": gov})
    # depositing DAI to generate crv3 tokens.
    #crv3.approve(crv3_liquidity, Wei("1000000 ether"), {"from": crv3_liquidity})
    threePool.add_liquidity([0, 0, 200000000000, 0, {"from": gov})
    #giving Gov some shares to mimic profit
    #yCRV3.depositAll({"from": gov})

    # users deposit to vault
    yUSDT3.deposit(1000000000, {"from": bob})
    yUSDT3.deposit(4000000000, {"from": alice})
    yUSDT3.deposit(10000000, {"from": tinytim})

    a = yUSDT3.pricePerShare()

    chain.mine(1)

    strategy.harvest({"from": gov})
    chain.mine(10)

    # small profit
    #yCRV3.approve(gov, Wei("1000000 ether"), {"from": gov})
    #yCRV3.transferFrom(gov, strategy, Wei("5000 ether"), {"from": gov})
    #crv3Strat.harvest({"from": crv3StratOwner})
    usdt.transferFrom(gov, strategy, 5000000000, {"from": gov})
    strategy.harvest({"from": gov})
    chain.mine(10)
    strategy.harvest({"from": gov})
    chain.mine(10)

    b = yUSDT3.pricePerShare()

    assert b > a

    #withdrawals have a slippage protection parameter, defaults to 1 = 0.01%.
    #overwriting here to be 0.75%, to account for slippage + 0.5% v1 vault withdrawal fee.
    #d = yUSDT3.balanceOf(alice)

    c = yUSDT3.balanceOf(alice)

    yUSDT3.withdraw(c, alice, 75, {"from": alice})

    assert usdt.balanceOf(alice) > 0
    assert usdt.balanceOf(strategy) == 0
    assert usdt.balanceOf(bob) == 0
    assert yCRV3.balanceOf(strategy) > 0

    d = yUSDT3.balanceOf(bob)
    yUSDT3.withdraw(d, bob, 75, {"from": bob})

    assert usdt.balanceOf(bob) > 0
    assert usdt.balanceOf(strategy) == 0

    e = yUSDT3.balanceOf(tinytim)
    yUSDT3.withdraw(e, tinytim, 75, {"from": tinytim})

    assert usdt.balanceOf(tinytim) > 0
    assert usdt.balanceOf(strategy) == 0

    # We should have made profit
    assert yUSDT3.pricePerShare() > 1

    pass

    ##crv3.transferFrom(gov, bob, Wei("100000 ether"), {"from": gov})
    ##crv3.transferFrom(gov, alice, Wei("788000 ether"), {"from": gov})

    # yUSDT.deposit(Wei("100000 ether"), {"from": bob})
    # yUSDT.deposit(Wei("788000 ether"), {"from": alice})

    # strategy.harvest()

    # assert dai.balanceOf(strategy) == 0
    # assert yUSDT3.balanceOf(strategy) > 0
    # assert ycrv3.balanceOf(strategy) > 0