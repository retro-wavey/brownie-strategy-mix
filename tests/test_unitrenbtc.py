# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")
import pytest
import time
from brownie import Wei, accounts, Contract, config, interface, chain
from brownie import StrategyUnitRenbtcV1, MMVault, ControllerV3

@pytest.fixture
def mmDeployer(accounts):
    yield accounts.at("0x43229759E12eFbe3e2A0fB0510B15e516d046442", force=True)
    
@pytest.fixture
def mmTimelock(accounts):
    yield accounts.at("0x5DAe9B27313670663B34Ac8BfFD18825bB9Df736", force=True)
    
@pytest.fixture
def renbtcWhale(accounts):
    yield accounts.at("0x4f6a43ad7cba042606decaca730d4ce0a57ac62e", force=True)
    
@pytest.fixture
def usdpWhale(accounts):
    yield accounts.at("0x0fef2f14127a2a290256523905e39dc817c11e42", force=True)
   
@pytest.fixture
def renbtcToken(interface):
    yield interface.IERC20("0xEB4C2781e4ebA804CE9a9803C67d0893436bB27D")
   
@pytest.fixture
def mmController(pm, mmDeployer):
    mmController = mmDeployer.deploy(ControllerV3, mmDeployer, mmDeployer, mmDeployer, mmDeployer, mmDeployer)
    # mmController = interface.MMController("0x4bf5059065541a2b176500928e91fbfd0b121d07")
    yield mmController
   
@pytest.fixture
def renbtcVault(pm, renbtcToken, mmDeployer, mmController):
    renbtcVault = mmDeployer.deploy(MMVault, renbtcToken, mmDeployer, mmDeployer, mmController)
    # renbtcVault = interface.MMVault("0x076950237f8c0D27Ac25694c9078F96e535723BC")
    
    if(mmController.vaults(renbtcToken) == "0x0000000000000000000000000000000000000000"):    
       mmController.setVault(renbtcToken, renbtcVault, {"from": mmDeployer})
    
    yield renbtcVault
 
@pytest.fixture
def renbtcStrategy(pm, renbtcToken, mmDeployer, mmController, mmTimelock):
    renbtcStrategy = mmDeployer.deploy(StrategyUnitRenbtcV1, mmDeployer, mmDeployer, mmController, mmDeployer)
    # renbtcStrategy = interface.MMStrategy("0x27BF4D326A4F11A11A72A07F38DA64D2F502A23B")   
    mmController.approveStrategy(renbtcToken, renbtcStrategy, {"from": mmDeployer}) 
    # mmController.approveStrategy(renbtcToken, renbtcStrategy, {"from": mmTimelock}) 
    mmController.setStrategy(renbtcToken, renbtcStrategy, {"from": mmDeployer})
    renbtcStrategy.setBuybackEnabled(False, {"from": mmDeployer})
    renbtcStrategy.setDelayBlockRequired(False, {"from": mmDeployer})
    yield renbtcStrategy
    
@pytest.mark.require_network("mainnet-fork")
def test_normal_flow(pm, mmDeployer, renbtcWhale, renbtcToken, renbtcVault, renbtcStrategy, usdpWhale):
         
    # store original balance too compare
    prevBal = renbtcToken.balanceOf(renbtcWhale) 
    
    # deposit -> harvest    
    amount = 100 * 1e8
    _depositAndHarvest(mmDeployer, renbtcWhale, renbtcToken, renbtcVault, renbtcStrategy, amount)
    
    # Aha, we got vault appreciation by yielding $CRV!
    assert renbtcStrategy.lastHarvestInWant() > 0 
    
    # super-sugar-daddy some CDP fee
    usdp = interface.IERC20(renbtcStrategy.debtToken())
    usdp.transfer(renbtcStrategy, 100000 * 1e18, {'from':usdpWhale})
    
    # ensure we could keepMinRatio and majority usdp from sugar-daddy will be used by keepMinRatio
    renbtcStrategy.setMinRatio(210, {"from": mmDeployer})
    renbtcStrategy.keepMinRatio({"from": mmDeployer})
    assert renbtcStrategy.currentRatio() > 210
    
    # withdraw  
    _wantTokenBefore = renbtcToken.balanceOf(renbtcWhale)  
    shareDivisor = 2
    _withdraw(renbtcWhale, renbtcVault, shareDivisor)  
    _wantTokenAfter = renbtcToken.balanceOf(renbtcWhale) 
    
    # we should have made some profit ignoring the fee
    assert (_wantTokenAfter - _wantTokenBefore) > _deduct_mushrooms_fee(amount / shareDivisor)
    
    # withdraw all rest 
    _withdraw(renbtcWhale, renbtcVault, 1)
    assert renbtcVault.totalSupply() == 0
    
    # deposit again
    renbtcVault.deposit(amount, {"from": renbtcWhale})     
    assert renbtcVault.balanceOf(renbtcWhale) == amount
    
    
@pytest.mark.require_network("mainnet-fork")
def test_withdraw_all(pm, mmDeployer, renbtcWhale, renbtcToken, renbtcVault, renbtcStrategy, mmController, usdpWhale):
         
    # store original balance too compare
    prevBal = renbtcToken.balanceOf(renbtcWhale) 
    
    # deposit -> harvest   
    amount = 100 * 1e8
    _depositAndHarvest(mmDeployer, renbtcWhale, renbtcToken, renbtcVault, renbtcStrategy, amount)
    
    # Aha, we got vault appreciation by yielding $CRV!
    assert renbtcStrategy.lastHarvestInWant() > 0 
    
    # sugar-daddy some CDP fee
    usdp = interface.IERC20(renbtcStrategy.debtToken())
    usdp.transfer(renbtcStrategy, 10000 * 1e18, {'from':usdpWhale})
    
    # withdraw all from strategy  
    mmController.withdrawAll(renbtcToken, {"from": mmDeployer})  
    # rough estimate due to unit protocol
    assert renbtcToken.balanceOf(renbtcVault) >= (amount)


####################### test dependent functions ########################################

def _reserve_mushrooms_vault(amount):
    # there is a reserve buffer in Mushrooms vaults
    return amount * 0.05

def _deduct_mushrooms_fee(amount):
    # deduct the withdraw fee (0.2% = 20 BPS) from Mushrooms vaults
    return amount * 0.998
 
def _depositAndHarvest(mmDeployer, renbtcWhale, renbtcToken, renbtcVault, renbtcStrategy, depositAmount):
    renbtcToken.approve(renbtcVault, 1000_000_000_000 * 1e8, {"from": renbtcWhale})
    
    renbtcVault.deposit(depositAmount, {"from": renbtcWhale})     
    assert renbtcVault.balanceOf(renbtcWhale) == depositAmount
    
    bal = renbtcToken.balanceOf(renbtcVault)
    renbtcVault.earn({"from": mmDeployer})   
    assert renbtcToken.balanceOf(renbtcVault) <= _reserve_mushrooms_vault(bal)  

    endMineTime = (int)(time.time() + 3600 * 1) # mine to 1 hour
    chain.mine(blocks=200, timestamp=endMineTime) 
    
    claimable = renbtcStrategy.getHarvestable.call({"from": mmDeployer})
    assert claimable > 0
    
    renbtcStrategy.harvest({"from": mmDeployer}) 

def _withdraw(renbtcWhale, renbtcVault, shareDivisor):
    shareAmount = renbtcVault.balanceOf(renbtcWhale)
    renbtcVault.withdraw(shareAmount / shareDivisor, {"from": renbtcWhale})     
    assert renbtcVault.balanceOf(renbtcWhale) == shareAmount - (shareAmount / shareDivisor)

