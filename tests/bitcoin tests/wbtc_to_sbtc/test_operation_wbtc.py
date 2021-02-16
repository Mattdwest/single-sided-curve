# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")

import pytest

from brownie import Wei, accounts, Contract, config
from brownie import StrategyWBTCsBTCv2


@pytest.mark.require_network("mainnet-fork")
def test_operation(pm, chain):
    wbtc_liquidity = accounts.at(
        "0x93054188d876f558f4a66b2ef1d97d16edf0895b", force=True
    )  # using curve pool (lots of wbtc)

    sbtc_liquidity =  accounts.at(
        "0x13c1542a468319688b89e323fe9a3be3a90ebb27", force=True
    )  # synthetix (lots of sbtc)

    rewards = accounts[2]
    gov = accounts[3]
    guardian = accounts[4]
    bob = accounts[5]
    alice = accounts[6]
    strategist = accounts[7]
    tinytim = accounts[8]

    wbtc = Contract("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599", owner=gov)  # wbtc token

    wbtc.approve(wbtc_liquidity, Wei("1000000 ether"), {"from": wbtc_liquidity})
    wbtc.transferFrom(wbtc_liquidity, gov, 3000000000, {"from": wbtc_liquidity})

    sbtc = Contract(
        "0x075b1bb99792c9E1041bA13afEf80C91a1e70fB3", owner=gov
    )  # sbtcCRV token address (threePool)

    sbtc.approve(sbtc_liquidity, Wei("1000000 ether"), {"from": sbtc_liquidity})
    sbtc.transferFrom(sbtc_liquidity, gov, Wei("100 ether"), {"from": sbtc_liquidity})

    # config vault.
    Vault = pm(config["dependencies"][0]).Vault
    yUSDT3 = Vault.deploy({"from": gov})
    yUSDT3.initialize(wbtc, gov, rewards, "", "")
    yUSDT3.setDepositLimit(Wei("1000000 ether"))

    sbtcPool = Contract(
        "0x7fC77b5c7614E1533320Ea6DDc2Eb61fa00A9714", owner=gov
    )  # sbtcCRV pool address (threePool)
    ysBTC = Contract(
        "0x7Ff566E1d69DEfF32a7b244aE7276b9f90e9D0f6", owner=gov
    )  # sbtc vault (threePool)
    crv3Strat = Contract(
        "0x6D6c1AD13A5000148Aa087E7CbFb53D402c81341", owner=gov
    )  # crv3 strat (threePool)
    crv3StratOwner = Contract(
        "0xd0aC37E3524F295D141d3839d5ed5F26A40b589D", owner=gov
    )  # crv3 stratOwner (threePool)
    # uni = Contract.from_explorer(
    #  "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", owner=gov
    # )  # UNI router v2

    strategy = guardian.deploy(StrategyWBTCsBTCv2, yUSDT3, wbtc, sbtcPool, ysBTC, sbtc)
    strategy.setStrategist(strategist)

    yUSDT3.addStrategy(
        strategy, 10_000, 0, 0, {"from": gov}
    )

    wbtc.approve(gov, Wei("1000000 ether"), {"from": gov})
    wbtc.transferFrom(gov, bob, 100000000, {"from": gov})
    wbtc.transferFrom(gov, alice, 1000000000, {"from": gov})
    wbtc.transferFrom(gov, tinytim, 1000000, {"from":gov})
    wbtc.approve(yUSDT3, Wei("1000000 ether"), {"from": bob})
    wbtc.approve(yUSDT3, Wei("1000000 ether"), {"from": alice})
    wbtc.approve(yUSDT3, Wei("1000000 ether"), {"from": tinytim})
    sbtc.approve(gov, Wei("1000000 ether"), {"from": gov})
    yUSDT3.approve(gov, Wei("1000000 ether"), {"from": gov})
    sbtc.approve(ysBTC, Wei("1000000 ether"), {"from": gov})
    wbtc.approve(sbtcPool, Wei("1000000 ether"), {"from": gov})

    wbtc.approve(sbtcPool, Wei("1000000 ether"), {"from": gov})
    # depositing DAI to generate crv3 tokens.
    #crv3.approve(crv3_liquidity, Wei("1000000 ether"), {"from": crv3_liquidity})
    #threePool.add_liquidity([0, 200000000000, 0], 0, {"from": gov})
    #giving Gov some shares to mimic profit
    #yCRV3.depositAll({"from": gov})

    # users deposit to vault
    yUSDT3.deposit(100000000, {"from": bob})
    yUSDT3.deposit(1000000000, {"from": alice})
    yUSDT3.deposit(1000000, {"from": tinytim})

    

    chain.mine(1)

    strategy.harvest({"from": gov})

    strategy.harvest({"from": gov})

    assert ysBTC.balanceOf(strategy) > 0
    chain.sleep(3600*24*7*10)
    chain.mine(1)
    a = yUSDT3.pricePerShare()

    # small profit
    #yCRV3.approve(gov, Wei("1000000 ether"), {"from": gov})
    #yCRV3.transferFrom(gov, strategy, Wei("5000 ether"), {"from": gov})
    t = ysBTC.getPricePerFullShare()
    c = strategy.estimatedTotalAssets()
    crv3Strat.harvest({"from": crv3StratOwner})
    s = ysBTC.getPricePerFullShare()
    d = strategy.estimatedTotalAssets()
    assert t < s
    assert d > c

    assert yUSDT3.strategies(strategy).dict()['totalDebt'] < d

    #wbtc.transferFrom(gov, strategy, 500000000, {"from": gov})
    #strategy.harvest({"from": gov})
    #chain.mine(1)
    strategy.harvest({"from": gov})
    chain.mine(1)

    b = yUSDT3.pricePerShare()

    # debt rises faster than profit based on the mainnet fork due to a very low ~1.5% APY on this curve pool at the moment.
    # as long as b!= a, then it is tracking profit/losses value/debt as these values diverge
    assert b != a

    #withdrawals have a slippage protection parameter, defaults to 1 = 0.01%.
    #overwriting here to be 0.75%, to account for slippage + 0.5% v1 vault withdrawal fee.
    #d = yUSDT3.balanceOf(alice)

    c = yUSDT3.balanceOf(alice)

    yUSDT3.withdraw(c, alice, 75, {"from": alice})

    assert wbtc.balanceOf(alice) > 0
    assert wbtc.balanceOf(bob) == 0
    assert ysBTC.balanceOf(strategy) > 0

    d = yUSDT3.balanceOf(bob)
    yUSDT3.withdraw(d, bob, 75, {"from": bob})

    assert wbtc.balanceOf(bob) > 0

    e = yUSDT3.balanceOf(tinytim)
    yUSDT3.withdraw(e, tinytim, 75, {"from": tinytim})

    assert wbtc.balanceOf(tinytim) > 0

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