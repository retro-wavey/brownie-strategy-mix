# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")
import pytest
import time
from brownie import Wei, accounts, Contract, config, interface, chain
from brownie import StrategyAlchemixALCX, MMVault, ControllerV3

@pytest.fixture
def mmDeployer(accounts):
    yield accounts.at("0x43229759E12eFbe3e2A0fB0510B15e516d046442", force=True)
    
@pytest.fixture
def alcxWhale(accounts):
    yield accounts.at("0x6206E425BC584AC757E28BCc5555a44Ace4bCfa0", force=True)
   
@pytest.fixture
def alcxToken(interface):
    yield interface.IERC20("0xdBdb4d16EdA451D0503b854CF79D55697F90c8DF")
   
@pytest.fixture
def mmController(pm, mmDeployer):
    mmController = mmDeployer.deploy(ControllerV3, mmDeployer, mmDeployer, mmDeployer, mmDeployer, mmDeployer)
    # TODO use mainnet controller
    yield mmController
   
@pytest.fixture
def alcxVault(pm, alcxToken, mmDeployer, mmController):
    alcxVault = mmDeployer.deploy(MMVault, alcxToken, mmDeployer, mmDeployer, mmController)
    # TODO use mainnet vault
    mmController.setVault(alcxToken, alcxVault, {"from": mmDeployer})
    yield alcxVault
 
@pytest.fixture
def alcxStrategy(pm, alcxToken, mmDeployer, mmController):
    alcxStrategy = mmDeployer.deploy(StrategyAlchemixALCX, mmDeployer, mmDeployer, mmController, mmDeployer)
    mmController.approveStrategy(alcxToken, alcxStrategy, {"from": mmDeployer}) 
    # TODO use mainnet strategy     
    mmController.setStrategy(alcxToken, alcxStrategy, {"from": mmDeployer})
    alcxStrategy.setBuybackEnabled(False)
    yield alcxStrategy
    
@pytest.mark.require_network("mainnet-fork")
def test_normal_flow(pm, mmDeployer, alcxWhale, alcxToken, alcxVault, alcxStrategy):
         
    # store original balance too compare
    prevBal = alcxToken.balanceOf(alcxWhale) 
    
    # deposit -> harvest    
    amount = 200 * 1e18
    _depositAndHarvest(mmDeployer, alcxWhale, alcxToken, alcxVault, alcxStrategy, amount)
    
    # Aha, we got vault appreciation by yielding $ALCX!
    assert alcxVault.getRatio() > 1e18 
    
    # withdraw   
    _withdraw(alcxWhale, alcxToken, alcxVault)  
    assert alcxVault.totalSupply() == 0  
    
    # we should have made some profit ignoring the fee
    postBal = alcxToken.balanceOf(alcxWhale) 
    assert postBal > _deduct_mushrooms_fee(prevBal) 
    
@pytest.mark.require_network("mainnet-fork")
def test_withdraw_all(pm, mmDeployer, alcxWhale, alcxToken, alcxVault, alcxStrategy, mmController):
         
    # store original balance too compare
    prevBal = alcxToken.balanceOf(alcxWhale) 
    
    # deposit -> harvest   
    amount = 200 * 1e18
    _depositAndHarvest(mmDeployer, alcxWhale, alcxToken, alcxVault, alcxStrategy, amount)
    
    # Aha, we got vault appreciation by yielding $ALCX!
    assert alcxVault.getRatio() > 1e18 
    
    # withdraw all from strategy  
    mmController.withdrawAll(alcxToken)  
    assert alcxToken.balanceOf(alcxVault) >= amount 


####################### test dependent functions ########################################

def _reserve_mushrooms_vault(amount):
    # there is a reserve buffer in Mushrooms vaults
    return amount * 0.05

def _deduct_mushrooms_fee(amount):
    # deduct the withdraw fee (0.2% = 20 BPS) from Mushrooms vaults
    return amount * 0.998
 
def _depositAndHarvest(mmDeployer, alcxWhale, alcxToken, alcxVault, alcxStrategy, depositAmount):
    alcxToken.approve(alcxVault, 1000_000_000_000 * 1e18, {"from": alcxWhale})
    
    alcxVault.deposit(depositAmount, {"from": alcxWhale})     
    assert alcxVault.balanceOf(alcxWhale) == depositAmount
    
    alcxVault.earn({"from": mmDeployer})   
    assert alcxToken.balanceOf(alcxVault) <= _reserve_mushrooms_vault(depositAmount)  

    endMineTime = (int)(time.time() + 2592000 * 1) # mine to 30 days later
    chain.mine(blocks=300, timestamp=endMineTime) 
    
    alcxStrategy.harvest({"from": mmDeployer}) 

def _withdraw(alcxWhale, alcxToken, alcxVault):
    shareAmount = alcxVault.balanceOf(alcxWhale)
    alcxVault.withdraw(shareAmount, {"from": alcxWhale})     
    assert alcxVault.balanceOf(alcxWhale) == 0    

