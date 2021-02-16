# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")

import pytest

from brownie import Wei, accounts, Contract, config
from brownie import StrategyDAImUSDv2


@pytest.mark.require_network("mainnet-fork")
def test_operation(pm, chain):
    dai_liquidity = accounts.at(
        "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7", force=True
    )  # using curve pool (lots of dai)

    crv3_liquidity =  accounts.at(
        "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490", force=True
    )  # yearn treasury (lots of crv3)

    #altCRV_liquidity = accounts.at(
    #    "0x907ebd0ddfd74fdaa1abb8a7e2294475e179a9ea", force=True
    #)  # giant amount

    rewards = accounts[2]
    gov = accounts[3]
    guardian = accounts[4]
    bob = accounts[5]
    alice = accounts[6]
    strategist = accounts[7]
    tinytim = accounts[8]

    dai = Contract("0x6b175474e89094c44da98b954eedeac495271d0f", owner=gov)  # DAI token

    dai.approve(dai_liquidity, Wei("1000000 ether"), {"from": dai_liquidity})
    dai.transferFrom(dai_liquidity, gov, Wei("300000 ether"), {"from": dai_liquidity})

    crv3 = Contract(
        "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490", owner=gov
    )  # crv3 token address (threePool)

    altCRV = Contract(
        "0xD2967f45c4f384DEEa880F807Be904762a3DeA07", owner=gov
    )  # altCRV token (gUSDCrv)

    crv3.approve(crv3_liquidity, Wei("1000000 ether"), {"from": crv3_liquidity})
    crv3.transferFrom(crv3_liquidity, gov, Wei("100 ether"), {"from": crv3_liquidity})

    #altCRV.approve(altCRV_liquidity, Wei("1000000 ether"), {"from": altCRV_liquidity})
    #altCRV.transferFrom(altCRV_liquidity, gov, Wei("1000 ether"), {"from": altCRV_liquidity})

    # config dai vault.
    Vault = pm(config["dependencies"][0]).Vault
    yDAI = Vault.deploy({"from": gov})
    yDAI.initialize(dai, gov, rewards, "", "",{"from": gov})
    yDAI.setDepositLimit(Wei("1000000 ether"))

    threePool = Contract(
        "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7", owner=gov
    )  # crv3 pool address (threePool)
    altCrvPool = Contract(
        "0x4f062658EaAF2C1ccf8C8e36D6824CDf41167956", owner=gov
    )  # atlCrvPool pool address (gusdCrv)
    targetVault = Contract(
        "0xcC7E70A958917cCe67B4B87a8C30E6297451aE98", owner=gov
    )  # target vault (gusdCrv)
    targetVaultStrat = Contract(
        "0xD42eC70A590C6bc11e9995314fdbA45B4f74FABb", owner=gov
    )  # targetVault strat (gusd)
    targetVaultStratOwner = Contract(
        "0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", owner=gov
    )  # targetVault stratOwner (threePool)


    strategy = guardian.deploy(StrategyDAImUSDv2, yDAI, dai, threePool, targetVault, crv3, altCRV, altCrvPool)
    strategy.setStrategist(strategist)

    yDAI.addStrategy(
        strategy, 10_000, 0, 0, {"from": gov}
    )

    dai.approve(gov, Wei("1000000 ether"), {"from": gov})
    dai.transferFrom(gov, bob, Wei("1000 ether"), {"from": gov})
    dai.transferFrom(gov, alice, Wei("4000 ether"), {"from": gov})
    dai.transferFrom(gov, tinytim, Wei("10 ether"), {"from":gov})
    dai.approve(yDAI, Wei("1000000 ether"), {"from": bob})
    dai.approve(yDAI, Wei("1000000 ether"), {"from": alice})
    dai.approve(yDAI, Wei("1000000 ether"), {"from": tinytim})
    crv3.approve(gov, Wei("1000000 ether"), {"from": gov})
    yDAI.approve(gov, Wei("1000000 ether"), {"from": gov})
    targetVault.approve(gov, Wei("1000000 ether"), {"from": gov})
    altCRV.approve(gov, Wei("1000000 ether"), {"from": gov})
    dai.approve(threePool, Wei("1000000 ether"), {"from": gov})
    crv3.approve(altCrvPool, Wei("1000000 ether"), {"from": gov})

    targetVaultStrat.setStrategistReward(0, {"from": targetVaultStratOwner})
    targetVaultStrat.setTreasuryFee(0, {"from": targetVaultStratOwner})
    targetVaultStrat.setWithdrawalFee(0, {"from": targetVaultStratOwner})

    # users deposit to vault
    yDAI.deposit(Wei("1000 ether"), {"from": bob})
    yDAI.deposit(Wei("4000 ether"), {"from": alice})
    yDAI.deposit(Wei("10 ether"), {"from": tinytim})

    a = yDAI.pricePerShare()

    chain.mine(1)

    strategy.harvest({"from": gov})

    assert targetVault.balanceOf(strategy) > 0
    chain.sleep(3600*24*7*10)
    chain.mine(1)
    a = yDAI.pricePerShare()

    # small profit
    t = targetVault.getPricePerFullShare()
    c = strategy.estimatedTotalAssets()
    targetVaultStrat.harvest({"from": targetVaultStratOwner})
    s = targetVault.getPricePerFullShare()
    d = strategy.estimatedTotalAssets()
    assert t < s
    assert d > c

    assert yDAI.strategies(strategy).dict()['totalDebt'] < d

    strategy.harvest({"from": gov})
    chain.mine(1)

    b = yDAI.pricePerShare()

    assert b > a

    #withdrawals have a slippage protection parameter, defaults to 1 = 0.01%.
    #overwriting here to be 1.5%, to account for slippage from multiple hops.
    #slippage also counts "beneficial" slippage, such as DAI being overweight in these pools
    #d = yUSDT3.balanceOf(alice)

    c = yDAI.balanceOf(alice)


    yDAI.withdraw(c, alice, 150, {"from": alice})

    assert dai.balanceOf(alice) > 0
    assert dai.balanceOf(strategy) == 0
    assert dai.balanceOf(bob) == 0
    assert targetVault.balanceOf(strategy) > 0

    d = yDAI.balanceOf(bob)
    yDAI.withdraw(d, bob, 150, {"from": bob})

    assert dai.balanceOf(bob) > 0
    assert dai.balanceOf(strategy) == 0

    e = yDAI.balanceOf(tinytim)
    yDAI.withdraw(e, tinytim, 150, {"from": tinytim})

    assert dai.balanceOf(tinytim) > 0
    assert dai.balanceOf(strategy) == 0

    # We should have made profit
    assert yDAI.pricePerShare() > 1

    #print("\ntinytim", dai.balanceOf(tinytim)/1e18)
    #print("\nbob", dai.balanceOf(bob)/1e18)
    #print("\nalice", dai.balanceOf(alice)/1e18)
    #print("\nvault", targetVault.balanceOf(strategy)/1e18)

    assert 1 == 2

    pass
