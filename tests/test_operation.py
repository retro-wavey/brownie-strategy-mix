# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")
import pytest
import time
from brownie import Wei, accounts, Contract, config, interface, chain
from brownie import Strategy

def test_operation(pm):
      
    wbtcAddr = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599";
    depositAmount = 1000000 # 0.01 wbtc with decimal is 8
    wbtc = interface.IERC20(wbtcAddr)
    
    # assume this is also a keeper for Mushrooms vault/strategy and enough eth for contract deployment
    tester = accounts.add('27cdd8910449bea9f4e61e6c1ffb2cd173bebf59b7fe7c923a5851b2df4c6e66')
    gov = tester    
    prevBal = wbtc.balanceOf(tester)
    
    # gov: deploy yVault for wbtc
    vaultLimit = 100000000000000;  # 1 million allowance wbtc with decimal is 8
    Vault = pm("iearn-finance/yearn-vaults@0.3.0").Vault
    yWbtc = Vault.deploy({"from": gov})
    yWbtc.initialize(wbtcAddr, gov, gov, "", "", {"from": gov})
    yWbtc.setDepositLimit(vaultLimit, {"from": gov}) 
    
    ########################################################################
    ###  yVault : deposit -> harvest
    ########################################################################
    
    # gov: deploy wbtc strategy to yield in Mushrooms
    strategy = gov.deploy(Strategy, yWbtc)
    # gov：add strategy with 100% BPS allocation + no rate limit + no fee 
    yWbtc.addStrategy(strategy, 10_000, 0, 0, {"from": gov})  
                
    # deposit want token and yield some    
    assetTotal = _deposit_and_harvest(yWbtc, strategy, tester, wbtc, depositAmount, vaultLimit, gov, tester, (int)(time.time() + 2592000 * 1))
    
    ########################################################################
    ###  yVault : migration
    ########################################################################
    
    # gov: deploy a new wbtc strategy for migration
    strategyNew = gov.deploy(Strategy, yWbtc) 
       
    # gov: migrate to new yStrategy
    yWbtc.migrateStrategy(strategy, strategyNew, {"from": gov})       
    assetMigrated = strategyNew.estimatedTotalAssets()    
    assert assetMigrated >= assetTotal
    
    ########################################################################
    ###  yVault : withdraw
    ########################################################################
        
    # tester: withdraw all from yVault, possible maxLoss BPS considering withdraw fee (0.2%) from Mushrooms vaults
    yWbtc.withdraw(depositAmount, tester, 21, {"from": tester})
    postBal = wbtc.balanceOf(tester)
    
    # we should have made some profit ignoring the withdraw fee (0.2%) from Mushrooms vaults
    assert postBal > (prevBal * 0.998) 
    
def _deposit_and_harvest(yVault, yStrategy, tester, want, depositAmount, allowLimit, yStrategist, mStrategist, endMineTime):
    # tester: deposit want into yVault
    want.approve(yVault, 0, {"from": tester})
    want.approve(yVault, allowLimit, {"from": tester})
    yVault.deposit(depositAmount, {"from": tester})     
    assert yVault.balanceOf(tester) == depositAmount 
    
    # yStrategist: transfer want into Mushrooms for yield
    yStrategy.harvest({"from": yStrategist})

    # mStrategist: claim yield profit
    mmVault = interface.MMVault(yStrategy.mmVault())
    mmVault.earn({"from": mStrategist})    
    chain.mine(blocks=100, timestamp=endMineTime) 
    mmStrategy = interface.MMStrategy("0x4047093B9fD3F92415c938d0dC932117c801E08c");
    mmStrategy.harvest({"from": mStrategist})
    
    # yStrategist: claim yield profit from Mushrooms vault/strategy and Mushrooms farming pool
    yStrategy.harvest({"from": yStrategist})
    
    return yStrategy.estimatedTotalAssets()
    
    