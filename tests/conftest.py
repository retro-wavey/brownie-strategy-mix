import pytest
from brownie import config, accounts, Contract, chain, interface
from brownie import Strategy

@pytest.fixture
def andre(accounts):
    # Andre, giver of tokens, and maker of yield
    yield accounts[0]


@pytest.fixture
def token(andre, Token):
    yield andre.deploy(Token)


@pytest.fixture
def gov(accounts):
    # yearn multis... I mean YFI governance. I swear!
    yield accounts[1]


@pytest.fixture
def rewards(gov):
    yield gov  # TODO: Add rewards contract


@pytest.fixture
def guardian(accounts):
    # YFI Whale, probably
    yield accounts[2]


@pytest.fixture
def vault(pm, gov, rewards, guardian, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault, token, gov, rewards, "", "")
    yield vault


@pytest.fixture
def strategist(accounts):
    # You! Our new Strategist!
    yield accounts[3]


@pytest.fixture
def keeper(accounts):
    # This is our trusty bot!
    yield accounts[4]


@pytest.fixture
def strategy(strategist, keeper, vault, Strategy):
    strategy = strategist.deploy(Strategy, vault)
    strategy.setKeeper(keeper)
    yield strategy


@pytest.fixture
def nocoiner(accounts):
    # Has no tokens (DeFi is a ponzi scheme!)
    yield accounts[5]


@pytest.fixture
def pleb(accounts, andre, token, vault):
    # Small fish in a big pond
    a = accounts[6]
    # Has 0.01% of tokens (heard about this new DeFi thing!)
    bal = token.totalSupply() // 10000
    token.transfer(a, bal, {"from": andre})
    # Unlimited Approvals
    token.approve(vault, 2 ** 256 - 1, {"from": a})
    # Deposit half their stack
    vault.deposit(bal // 2, {"from": a})
    yield a


@pytest.fixture
def chad(accounts, andre, token, vault):
    # Just here to have fun!
    a = accounts[7]
    # Has 0.1% of tokens (somehow makes money trying every new thing)
    bal = token.totalSupply() // 1000
    token.transfer(a, bal, {"from": andre})
    # Unlimited Approvals
    token.approve(vault, 2 ** 256 - 1, {"from": a})
    # Deposit half their stack
    vault.deposit(bal // 2, {"from": a})
    yield a


@pytest.fixture
def greyhat(accounts, andre, token, vault):
    # Chaotic evil, will eat you alive
    a = accounts[8]
    # Has 1% of tokens (earned them the *hard way*)
    bal = token.totalSupply() // 100
    token.transfer(a, bal, {"from": andre})
    # Unlimited Approvals
    token.approve(vault, 2 ** 256 - 1, {"from": a})
    # Deposit half their stack
    vault.deposit(bal // 2, {"from": a})
    yield a


@pytest.fixture
def whale(accounts, andre, token, vault):
    # Totally in it for the tech
    a = accounts[9]
    # Has 10% of tokens (was in the ICO)
    bal = token.totalSupply() // 10
    token.transfer(a, bal, {"from": andre})
    # Unlimited Approvals
    token.approve(vault, 2 ** 256 - 1, {"from": a})
    # Deposit half their stack
    vault.deposit(bal // 2, {"from": a})
    yield a


########################################################################################
########## Mushrooms Integration: tests dependent fixtures
########################################################################################

@pytest.fixture
def yfiDeployer(accounts):
    yield accounts.at("0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7", force=True) # YFI dev multisig

@pytest.fixture
def wbtcWhale(accounts):
    yield accounts.at("0x875abe6F1E2Aba07bED4A3234d8555A0d7656d12", force=True)
    
@pytest.fixture
def mmKeeper(accounts):
    yield accounts.at("0x7cDaCBa026DDdAa0bD77E63474425f630DDf4A0D", force=True)
    
@pytest.fixture
def wbtcToken(interface):
    yield interface.IERC20("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599")
    
@pytest.fixture
def mmFarmingPool(interface):
    yield interface.MMFarmingPool("0xf8873a6080e8dbF41ADa900498DE0951074af577")
    
@pytest.fixture
def mmVault(interface):
    yield interface.MMVault("0xb06661A221Ab2Ec615531f9632D6Dc5D2984179A")
    
@pytest.fixture
def mmStrategy(interface):
    yield interface.MMStrategy("0xa6f43d225d188AeF31F99F20eBa8E537a6DE86B5")

@pytest.fixture
def yWbtc(pm, yfiDeployer, wbtcToken):
    vaultLimit = 1000_000_000 * 1e8
    Vault = pm("iearn-finance/yearn-vaults@0.3.2").Vault
    yWbtc = yfiDeployer.deploy(Vault) 
    yWbtc.initialize(wbtcToken, yfiDeployer, yfiDeployer, "", "", {"from": yfiDeployer})
    yWbtc.setDepositLimit(vaultLimit, {"from": yfiDeployer}) 
    yield yWbtc
 
@pytest.fixture
def yWbtcStrategy(yfiDeployer, yWbtc):
    yWbtcStrategy = yfiDeployer.deploy(Strategy, yWbtc)
    yWbtc.addStrategy(yWbtcStrategy, 10_000, 0, yWbtc.depositLimit(), 0, {"from": yfiDeployer})  
    vaultVersion = yWbtc.apiVersion()
    assert vaultVersion == "0.3.2"
    yield yWbtcStrategy
 
@pytest.fixture 
def yWbtcStrategyNew(yfiDeployer, yWbtc):
    yWbtcStrategyNew = yfiDeployer.deploy(Strategy, yWbtc)  
    yield yWbtcStrategyNew 
   
