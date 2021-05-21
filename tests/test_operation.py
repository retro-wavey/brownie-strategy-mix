# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")
import pytest
import time
from brownie import Wei, accounts, Contract, config, interface, chain
from brownie import Strategy

@pytest.mark.require_network("mainnet-fork")
def test_normal_flow(pm, yfiDeployer, wbtcWhale, mmKeeper, wbtcToken, yWbtc, yWbtcStrategy, mmFarmingPool, mmVault, mmStrategy):
         
    # store original balance too compare
    prevBal = wbtcToken.balanceOf(wbtcWhale) 
    
    # deposit -> harvest   
    depositAmount = _depositAndHarvest(yWbtc, wbtcWhale, wbtcToken, yWbtcStrategy, yfiDeployer, mmKeeper, mmVault, mmStrategy, 10_000_000)
                
    # Advancing blocks    
    chain.mine(blocks=300)   
    assert wbtcToken.balanceOf(yWbtc) == 0 # we already ape all in
    assert mmFarmingPool.pendingMM(11, yWbtcStrategy) > 0 # should have $MM to claim
    tx = yWbtcStrategy.harvest({"from": yfiDeployer})      
    assert len(tx.events['StrategyReported']) == 1 # we did the due report 
    assert mmFarmingPool.pendingMM(11, yWbtcStrategy) == 0  # NO $MM left to claim
    assert mmVault.balanceOf(yWbtcStrategy) == 0 # NO $MM left to swap
    assert wbtcToken.balanceOf(yWbtc) > 0 # Aha, we got vault appreciation by swapping $MM to want!
    
    # withdraw   
    _withdrawWbtc(yWbtc, wbtcWhale, wbtcToken)  
    assert yWbtc.totalSupply() > 0 # some earned fee turned into shares for governance/rewards  
    
    # we should have made some profit ignoring the fee
    postBal = wbtcToken.balanceOf(wbtcWhale) 
    assert postBal > _deduct_mushrooms_fee(prevBal) 
    
@pytest.mark.require_network("mainnet-fork")
def test_emergency_exit(pm, yfiDeployer, wbtcWhale, mmKeeper, wbtcToken, yWbtc, yWbtcStrategy, mmFarmingPool, mmVault, mmStrategy):
             
    # deposit -> harvest   
    depositAmount = _depositAndHarvest(yWbtc, wbtcWhale, wbtcToken, yWbtcStrategy, yfiDeployer, mmKeeper, mmVault, mmStrategy)
             
    # revoke -> emergencyExit -> harvest  
    yWbtcStrategy.setEmergencyExit({"from": yfiDeployer})
    yWbtcStrategy.harvest({"from": yfiDeployer})
    assert mmFarmingPool.userInfo(11, yWbtcStrategy)[0] == 0 # NO more staking left in farming pool
    assert mmVault.balanceOf(yWbtcStrategy) == 0 # NO more share left in mmVault
    assert yWbtcStrategy.estimatedTotalAssets() == 0
    
    # we should have returned almost all fund
    assert wbtcToken.balanceOf(yWbtc) >= _deduct_mushrooms_fee(depositAmount)
    
@pytest.mark.require_network("mainnet-fork")
def test_ratio_adjustment(pm, yfiDeployer, wbtcWhale, mmKeeper, wbtcToken, yWbtc, yWbtcStrategy, mmFarmingPool, mmVault, mmStrategy):
         
    # deposit -> harvest   
    depositAmount = _depositAndHarvest(yWbtc, wbtcWhale, wbtcToken, yWbtcStrategy, yfiDeployer, mmKeeper, mmVault, mmStrategy, 1000_000_000)
    
    # lower debtRatio from 10_000 to 5000  
    assert wbtcToken.balanceOf(yWbtc) == 0
    yWbtc.updateStrategyDebtRatio(yWbtcStrategy, 5000, {"from": yfiDeployer})
    # Advancing blocks  
    _mmEarnAndHarvest(mmKeeper, mmVault, mmStrategy)     
    chain.mine(blocks=300)
    yWbtcStrategy.harvest({"from": yfiDeployer})  
    
    # we should have returned nearly half of fund    
    assert wbtcToken.balanceOf(yWbtc) >= _deduct_mushrooms_fee(depositAmount) * (5000 / 10_000)
    
    # increase debtRatio from 5000 to 7500 
    yWbtc.updateStrategyDebtRatio(yWbtcStrategy, 7500, {"from": yfiDeployer})
    # Advancing blocks  
    _mmEarnAndHarvest(mmKeeper, mmVault, mmStrategy)     
    chain.mine(blocks=300)
    yWbtcStrategy.harvest({"from": yfiDeployer})          
    assert yWbtcStrategy.estimatedTotalAssets() >= _deduct_mushrooms_fee(depositAmount) * (7500 / 10_000)
    
@pytest.mark.require_network("mainnet-fork")
def test_strategy_migration(pm, yfiDeployer, wbtcWhale, mmKeeper, wbtcToken, yWbtc, yWbtcStrategy, yWbtcStrategyNew, mmFarmingPool, mmVault, mmStrategy):
             
    # store original balance too compare
    prevBal = wbtcToken.balanceOf(wbtcWhale)
    
    # deposit -> harvest   
    depositAmount = _depositAndHarvest(yWbtc, wbtcWhale, wbtcToken, yWbtcStrategy, yfiDeployer, mmKeeper, mmVault, mmStrategy)
    
    # migrate
    _migrationWbtcStrategy(yWbtc, yWbtcStrategy, yWbtcStrategyNew, yfiDeployer)
    
    # withdraw   
    _withdrawWbtc(yWbtc, wbtcWhale, wbtcToken)    
    
    # we should have made some profit ignoring the fee
    postBal = wbtcToken.balanceOf(wbtcWhale) 
    assert postBal > _deduct_mushrooms_fee(prevBal) 


####################### test dependent functions ########################################

def _deduct_mushrooms_fee(amount):
    # deduct the withdraw fee (0.2% = 20 BPS) from Mushrooms vaults
    return amount * 0.998
    
def _depositAndHarvest(yWbtc, wbtcWhale, wbtcToken, yWbtcStrategy, yfiDeployer, mmKeeper, mmVault, mmStrategy, depositAmount=1_000_000):
    depositAmount = _depositWbtc(yWbtc, wbtcWhale, wbtcToken, depositAmount)
    yWbtcStrategy.harvest({"from": yfiDeployer})    
    _mmEarnAndHarvest(mmKeeper, mmVault, mmStrategy)
    return depositAmount
 
def _depositWbtc(yWbtc, wbtcWhale, wbtcToken, depositAmount):
    wbtcToken.approve(yWbtc, 1000_000_000_000 * 1e18, {"from": wbtcWhale})
    yWbtc.deposit(depositAmount, {"from": wbtcWhale})     
    assert yWbtc.balanceOf(wbtcWhale) == depositAmount
    return depositAmount
       
def _mmEarnAndHarvest(mmKeeper, mmVault, mmStrategy): 
    mmVault.earn({"from": mmKeeper})    

    endMineTime = (int)(time.time() + 2592000 * 1) # mine to 30 days later
    chain.mine(blocks=100, timestamp=endMineTime) 
    
    mmStrategy.harvest({"from": mmKeeper})  

def _withdrawWbtc(yWbtc, wbtcWhale, wbtcToken):
    shareAmount = yWbtc.balanceOf(wbtcWhale)
    # possible maxLoss BPS considering withdraw fee (0.2% = 20 BPS) from Mushrooms vaults
    yWbtc.withdraw(shareAmount, wbtcWhale, 21, {"from": wbtcWhale})     
    assert yWbtc.balanceOf(wbtcWhale) == 0

def _migrationWbtcStrategy(yWbtc, yWbtcStrategy, yWbtcStrategyNew, yfiDeployer):      
    assetTotal = yWbtcStrategy.estimatedTotalAssets()    
    yWbtc.migrateStrategy(yWbtcStrategy, yWbtcStrategyNew, {"from": yfiDeployer})       
    assetMigrated = yWbtcStrategyNew.estimatedTotalAssets()    
    assert assetMigrated >= assetTotal

