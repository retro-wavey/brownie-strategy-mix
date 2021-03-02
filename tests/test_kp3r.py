# TODO: Add tests here that show the normal operation of this strategy
#       Suggestions to include:
#           - strategy loading and unloading (via Vault addStrategy/revokeStrategy)
#           - change in loading (from low to high and high to low)
#           - strategy operation at different loading levels (anticipated and "extreme")
import pytest
import time
from brownie import Wei, accounts, Contract, config, interface, chain
# from brownie import GenericKeep3rV2
    
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
    #genericKp3r = GenericKeep3rV2.deploy(kp3rToken, kp3rHelper, uniswapOracle, sushiswapOracle, mmController, {"from": mmDeployer}) # TODO use mainnet deployed fork
    genericKp3r = interface.MMGenericKp3r("0x0bD1d668d8E83d14252F2e01D5873df77A6511f0")
    
    if(interface.KP3RV1(kp3rToken).jobs(genericKp3r) == False):
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

@pytest.mark.require_network("mainnet-fork1")
def test_harvest(pm, mmDeployer, genericKp3r, kp3rStrategies):
    for strat in kp3rStrategies:
        _harvest(mmDeployer, genericKp3r, strat)
        
@pytest.mark.require_network("mainnet-fork1")
def test_keep_min_ratio(pm, mmDeployer, genericKp3r, kp3rCollateralizedStrategies):
    for strat in kp3rCollateralizedStrategies:
        _keepMinRatio(mmDeployer, genericKp3r, strat)
        
@pytest.mark.require_network("mainnet-fork1")
def test_earn(pm, mmDeployer, genericKp3r, kp3rVaults):
    for vault in kp3rVaults:
        _earn(mmDeployer, genericKp3r, vault)

@pytest.mark.require_network("mainnet-fork1")        
def test_add_remove(pm, mmDeployer, genericKp3r, kp3rStrategies, kp3rVaults):
    mDAI = interface.MMVault("0x6802377968857656fE8aE47fBECe76AaE588eeF7")
    mmDAIStrategy = interface.MMStrategy("0xc48E1e2a61121c84D96957e696A4A283615559d1")
    
    # Remove mmDAIStrategy & mDAI
    vaultsLenPreRemove = len(kp3rVaults)
    strategiesLenPreRemove = len(kp3rStrategies)
       
    genericKp3r.removeHarvestStrategy(mmDAIStrategy, {"from": mmDeployer})
    genericKp3r.removeEarnVault(mDAI, {"from": mmDeployer})

    assert (vaultsLenPreRemove - 1) == len(genericKp3r.getVaults())
    assert (strategiesLenPreRemove - 1) == len(genericKp3r.getStrategies())
    
    # Add back mDAI & mmDAIStrategy
    vaultsLenPreAdd = len(genericKp3r.getVaults())
    strategiesLenPreAdd = len(genericKp3r.getStrategies())
       
    genericKp3r.addVault(mDAI, 10000 * 1e18, {"from": mmDeployer})
    genericKp3r.addStrategy(mDAI, mmDAIStrategy, 700000, False, True, "0xc00e94Cb662C3520282E6f5717214004A7f26888", 1, {"from": mmDeployer})

    assert (vaultsLenPreAdd + 1) == len(genericKp3r.getVaults())
    assert (strategiesLenPreAdd + 1) == len(genericKp3r.getStrategies())
    _earn(mmDeployer, genericKp3r, mDAI)
    _harvest(mmDeployer, genericKp3r, mmDAIStrategy)

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
         
    

