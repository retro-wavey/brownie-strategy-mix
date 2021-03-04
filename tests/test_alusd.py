# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")
import pytest
import time
from brownie import Wei, accounts, Contract, config, interface, chain
from brownie import StrategyAlchemixALUSD, MMVault, ControllerV3

@pytest.fixture
def mmDeployer(accounts):
    yield accounts.at("0x43229759E12eFbe3e2A0fB0510B15e516d046442", force=True)
    
@pytest.fixture
def alusdWhale(accounts):
    yield accounts.at("0x4740fa6b32c5b41ebbf631fe1af41e6fff6e2388", force=True)
   
@pytest.fixture
def alusdToken(interface):
    yield interface.IERC20("0xBC6DA0FE9aD5f3b0d58160288917AA56653660E9")
   
@pytest.fixture
def mmController(pm, mmDeployer):
    mmController = mmDeployer.deploy(ControllerV3, mmDeployer, mmDeployer, mmDeployer, mmDeployer, mmDeployer)
    # TODO use mainnet controller
    yield mmController
   
@pytest.fixture
def alusdVault(pm, alusdToken, mmDeployer, mmController):
    alusdVault = mmDeployer.deploy(MMVault, alusdToken, mmDeployer, mmDeployer, mmController)
    # TODO use mainnet vault
    mmController.setVault(alusdToken, alusdVault, {"from": mmDeployer})
    yield alusdVault
 
@pytest.fixture
def alusdStrategy(pm, alusdToken, mmDeployer, mmController):
    alusdStrategy = mmDeployer.deploy(StrategyAlchemixALUSD, mmDeployer, mmDeployer, mmController, mmDeployer)
    mmController.approveStrategy(alusdToken, alusdStrategy, {"from": mmDeployer}) 
    # TODO use mainnet strategy     
    mmController.setStrategy(alusdToken, alusdStrategy, {"from": mmDeployer})
    alusdStrategy.setBuybackEnabled(False)
    yield alusdStrategy
    
@pytest.mark.require_network("mainnet-fork")
def test_normal_flow(pm, mmDeployer, alusdWhale, alusdToken, alusdVault, alusdStrategy):
         
    # store original balance too compare
    prevBal = alusdToken.balanceOf(alusdWhale) 
    
    # deposit -> harvest    
    amount = 40000 * 1e18
    _depositAndHarvest(mmDeployer, alusdWhale, alusdToken, alusdVault, alusdStrategy, amount)
    
    # Aha, we got vault appreciation by yielding $ALCX!
    assert alusdVault.getRatio() > 1e18 
    
    # withdraw   
    _withdraw(alusdWhale, alusdToken, alusdVault)  
    assert alusdVault.totalSupply() == 0  
    
    # we should have made some profit ignoring the fee
    postBal = alusdToken.balanceOf(alusdWhale) 
    assert postBal > _deduct_mushrooms_fee(prevBal) 
    
@pytest.mark.require_network("mainnet-fork")
def test_withdraw_all(pm, mmDeployer, alusdWhale, alusdToken, alusdVault, alusdStrategy, mmController):
         
    # store original balance too compare
    prevBal = alusdToken.balanceOf(alusdWhale) 
    
    # deposit -> harvest   
    amount = 40000 * 1e18
    _depositAndHarvest(mmDeployer, alusdWhale, alusdToken, alusdVault, alusdStrategy, amount)
    
    # Aha, we got vault appreciation by yielding $ALCX!
    assert alusdVault.getRatio() > 1e18 
    
    # withdraw all from strategy  
    mmController.withdrawAll(alusdToken)  
    assert alusdToken.balanceOf(alusdVault) >= amount 


####################### test dependent functions ########################################

def _reserve_mushrooms_vault(amount):
    # there is a reserve buffer in Mushrooms vaults
    return amount * 0.05

def _deduct_mushrooms_fee(amount):
    # deduct the withdraw fee (0.2% = 20 BPS) from Mushrooms vaults
    return amount * 0.998
 
def _depositAndHarvest(mmDeployer, alusdWhale, alusdToken, alusdVault, alusdStrategy, depositAmount):
    alusdToken.approve(alusdVault, 1000_000_000_000 * 1e18, {"from": alusdWhale})
    
    alusdVault.deposit(depositAmount, {"from": alusdWhale})     
    assert alusdVault.balanceOf(alusdWhale) == depositAmount
    
    alusdVault.earn({"from": mmDeployer})   
    assert alusdToken.balanceOf(alusdVault) <= _reserve_mushrooms_vault(depositAmount)  

    endMineTime = (int)(time.time() + 2592000 * 1) # mine to 30 days later
    chain.mine(blocks=300, timestamp=endMineTime) 
    
    alusdStrategy.harvest({"from": mmDeployer}) 

def _withdraw(alusdWhale, alusdToken, alusdVault):
    shareAmount = alusdVault.balanceOf(alusdWhale)
    alusdVault.withdraw(shareAmount, {"from": alusdWhale})     
    assert alusdVault.balanceOf(alusdWhale) == 0    

