# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")
import pytest
import time
from brownie import Wei, accounts, Contract, config, interface, chain
from brownie import GenericKeep3rV2
    
@pytest.fixture
def mmDeployer(accounts):
    yield accounts.at("0x43229759E12eFbe3e2A0fB0510B15e516d046442", force=True)
    
@pytest.fixture
def yearnDeployer(accounts):
    yield accounts.at("0x2D407dDb06311396fE14D4b49da5F0471447d45C", force=True)
   
@pytest.fixture
def mmController(interface):
    yield interface.MMController("0x4bF5059065541A2B176500928e91FBfD0B121d07")
   
@pytest.fixture
def kp3rToken(interface):
    yield interface.IERC20("0x1cEB5cB57C4D4E2b2433641b95Dd330A33185A44")
    
@pytest.fixture
def kp3rHelper(interface):
    yield interface.IKeep3rV1Helper("0x24e1565ED1D6530cd977A6A8B3e327b9F53A9fd2")
    
@pytest.fixture
def uniswapOracle(interface):
    yield interface.IUniswapV2SlidingOracle("0x73353801921417F465377c8d898c6f4C0270282C")
    
@pytest.fixture
def sushiswapOracle(interface):
    yield interface.IUniswapV2SlidingOracle("0xf67Ab1c914deE06Ba0F264031885Ea7B276a7cDa")

@pytest.fixture
def genericKp3r(pm, mmDeployer, yearnDeployer, mmController, kp3rToken, kp3rHelper, uniswapOracle, sushiswapOracle):
    genericKp3r = GenericKeep3rV2.deploy(kp3rToken, kp3rHelper, uniswapOracle, sushiswapOracle, mmController, {"from": mmDeployer}) # TODO use mainnet deployed fork
    
    interface.KP3RV1(kp3rToken).addJob(genericKp3r, {"from": yearnDeployer})
    interface.KP3RV1(kp3rToken).addKPRCredit(genericKp3r, 10000 * 1e18, {"from": yearnDeployer})
    
    strategies = interface.MMGenericKp3r(genericKp3r).getStrategies()
    for strat in strategies:
        _set_strategist(mmDeployer, genericKp3r, strat)
    
    vaults = interface.MMGenericKp3r(genericKp3r).getVaults() 
    for vault in vaults:
        # 3crv/crvrenwbtc/dai vault
        if (vault != "0x0c0291f4c12F04Da8B4139996C720a89D28Ca069" and vault != "0x1E074d6dA2987f0cb5A44F2Ab1C5BFeDdD81F23F" and vault != "0x6802377968857656fE8aE47fBECe76AaE588eeF7"):
            _add_keeper(mmDeployer, genericKp3r, vault)     
    
    yield genericKp3r
    
@pytest.fixture
def kp3rStrategies(pm, genericKp3r):    
    yield interface.MMGenericKp3r(genericKp3r).getStrategies()
    
@pytest.fixture
def kp3rCollateralizedStrategies(pm, genericKp3r):    
    yield interface.MMGenericKp3r(genericKp3r).getCollateralizedStrategies()
    
@pytest.fixture
def kp3rVaults(pm, genericKp3r):    
    yield interface.MMGenericKp3r(genericKp3r).getVaults()

@pytest.mark.require_network("mainnet-fork")
def test_harvest(pm, mmDeployer, genericKp3r, kp3rStrategies):
    for strat in kp3rStrategies:
        _harvest(mmDeployer, genericKp3r, strat)
        
@pytest.mark.require_network("mainnet-fork")
def test_keep_min_ratio(pm, mmDeployer, genericKp3r, kp3rCollateralizedStrategies):
    for strat in kp3rCollateralizedStrategies:
        _keepMinRatio(mmDeployer, genericKp3r, strat)
        
@pytest.mark.require_network("mainnet-fork")
def test_earn(pm, mmDeployer, genericKp3r, kp3rVaults):
    for vault in kp3rVaults:
        _earn(mmDeployer, genericKp3r, vault)

####################### test dependent functions ########################################

def _add_keeper(mmDeployer, genericKp3r, vault):
    interface.MMVault(vault).addKeeper(genericKp3r, {"from": mmDeployer})
    
def _set_strategist(mmDeployer, genericKp3r, strategy):
    interface.MMStrategy(strategy).setStrategist(genericKp3r, {"from": mmDeployer})
    
def _earn(mmDeployer, genericKp3r, vault):
    earnable = interface.MMGenericKp3r(genericKp3r).earnable(vault, {"from": mmDeployer})
    if(earnable):
       interface.MMGenericKp3r(genericKp3r).earn(vault, {"from": mmDeployer})
        
def _harvest(mmDeployer, genericKp3r, strategy):
    harvestable = interface.MMGenericKp3r(genericKp3r).harvestable.call(strategy, {"from": mmDeployer}) 
    if(harvestable):
       interface.MMGenericKp3r(genericKp3r).harvest(strategy, {"from": mmDeployer})     
    
def _keepMinRatio(mmDeployer, genericKp3r, strategy):
    interface.ICollateralizedStrategy(strategy).setMinRatio(350, {"from": mmDeployer})
    keepMinRatioMayday = interface.MMGenericKp3r(genericKp3r).keepMinRatioMayday(strategy, {"from": mmDeployer})
    if(keepMinRatioMayday):
       interface.MMGenericKp3r(genericKp3r).keepMinRatio(strategy, {"from": mmDeployer})
         
    

