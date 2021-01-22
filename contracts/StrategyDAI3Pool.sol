// SPDX-License-Identifier: MIT

pragma experimental ABIEncoderV2;
pragma solidity 0.6.12;

import "@openzeppelinV3/contracts/token/ERC20/IERC20.sol";
import "@openzeppelinV3/contracts/math/SafeMath.sol";
import "@openzeppelinV3/contracts/math/Math.sol";
import "@openzeppelinV3/contracts/utils/Address.sol";
import "@openzeppelinV3/contracts/token/ERC20/SafeERC20.sol";
import {BaseStrategy, StrategyParams} from "@yearnvaults/contracts/BaseStrategy.sol";

import "../../interfaces/curve/ICurve.sol";
import "../../interfaces/yearn/Vault.sol";


contract StrategyDAI3Pool is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    address public dai;
    address public threePool;
    address public y3Pool;
    address public unirouter;
    address public crv3;
    string public constant override name = "StrategyDAI3Pool";

    // adding protection against slippage attacks
    uint constant public DENOMINATOR = 10000;
    uint public slip = 100;

    // tracking value accrual
    uint public ppsTrack = 0;

    constructor(
        address _vault, // vault is v2, address is 0xBFa4D8AA6d8a379aBFe7793399D3DdaCC5bBECBB
        address _dai,
        address _threePool,
        address _y3Pool,
        address _crv3
    ) public BaseStrategy(_vault) {
        dai = _dai;
        threePool = _threePool;
        y3Pool = _y3Pool;
        crv3 = _crv3;

        IERC20(dai).safeApprove(threePool, uint256(-1));
        IERC20(crv3).safeApprove(y3Pool, uint256(-1));
    }

    function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](2);
        // dai (aka want) is already protected by default
        protected[0] = y3Pool;
        protected[1] = crv3;
        return protected;
    }

    // returns sum of all assets, realized and unrealized
    function estimatedTotalAssets() public override view returns (uint256) {
        return balanceOfWant().add(balanceOfStake()).add(balanceOfPool());
    }

    function prepareReturn(uint256 _debtOutstanding) internal override returns (uint256 _profit, uint256 _loss, uint256 _debtPayment) {
       // We might need to return want to the vault
        if (_debtOutstanding > 0) {
           uint256 _amountFreed = liquidatePosition(_debtOutstanding);
           _debtPayment = Math.min(_amountFreed, _debtOutstanding);
        }

        // harvest() does not require any action on behalf of this strategy, so we will track profit by estimated total assets.
        uint256 totalValueBefore = IERC20(y3Pool).balanceOf(address(this)).mul(ppsTrack);
        uint256 newPPS = Vault(y3Pool).getPricePerFullShare().div(1e18);
        uint256 totalValueAfter = IERC20(y3Pool).balanceOf(address(this)).mul(newPPS);
        uint256 _preProfit = totalValueAfter.sub(totalValueBefore);
        _profit = (_preProfit).mul(995).div(1000);
        setTrack();

        //harvest() also does not generate losses. Funds stay in yvCRV3 vault if not performing debt repayment.
        _loss == 0;

    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
       //emergency exit is dealt with in prepareReturn
        if (emergencyExit) {
          return;
       }

       // Invest the rest of the want
       uint256 _wantAvailable = balanceOfWant().sub(_debtOutstanding);
        if (_wantAvailable > 0) {
            uint256 _availableFunds = IERC20(dai).balanceOf(address(this));
            uint256 v = _availableFunds.mul(1e18).div(ICurve(threePool).get_virtual_price());
            ICurve(threePool).add_liquidity([_availableFunds,0,0], v.mul(DENOMINATOR.sub(slip)).div(DENOMINATOR));
            Vault(y3Pool).depositAll();
        }
    }

    // withdraws everything that is currently in the strategy, regardless of values.
    function exitPosition(uint256 _debtOutstanding)
        internal
        override
        returns (
          uint256 _profit,
          uint256 _loss,
          uint256 _debtPayment
        )
        {
        // to handle _debtOutstanding and _debtPayment
        if (_debtOutstanding > 0) {
           uint256 _amountFreed = liquidatePosition(_debtOutstanding);
           _debtPayment = Math.min(_amountFreed, _debtOutstanding);
        }

        // not including slippage protection for exitPosition due to its nature
        uint256 totalValueBefore = estimatedTotalAssets();
        Vault(y3Pool).withdrawAll();
        uint256 threePoolBalance = IERC20(crv3).balanceOf(address(this));
        ICurve(threePool).remove_liquidity_one_coin(threePoolBalance, 0, 0);
        uint256 totalValueAfter = estimatedTotalAssets();
        if (totalValueAfter > totalValueBefore) {
        _profit = totalValueAfter.sub(totalValueBefore);
        _loss == 0;
        }
        if (totalValueBefore > totalValueAfter) {
        _loss = totalValueBefore.sub(estimatedTotalAssets());
        _profit == 0;
        }
        }


    //this math only deals with want, which is dai.
    function liquidatePosition(uint256 _amountNeeded) internal override returns (uint256 _amountFreed) {
        if (balanceOfWant() < _amountNeeded) {
            // We need to sell stakes to get back more want
            _withdrawSome(_amountNeeded.sub(balanceOfWant()));
        }

        // Since we might free more than needed, let's send back the min
        _amountFreed = Math.min(balanceOfWant(), _amountNeeded);
    }


    // withdraw some dai from the vaults
    function _withdrawSome(uint256 _amount) internal returns (uint256) {
        uint256 balanceOfWantBefore = balanceOfWant();
        uint256 _3PoolAmount = (_amount).mul(1e18).div(ICurve(threePool).get_virtual_price());
        uint256 y3PoolAmount = (_3PoolAmount).mul(1e18).div(Vault(y3Pool).getPricePerFullShare());
        Vault(y3Pool).withdraw(y3PoolAmount);
        uint256 threePoolBalance = IERC20(crv3).balanceOf(address(this));
        uint256 v = threePoolBalance.mul(1e18).div(ICurve(threePool).get_virtual_price());
        ICurve(threePool).remove_liquidity_one_coin(threePoolBalance, 0, v);
        uint256 balanceAfter = balanceOfWant();
        return balanceAfter.sub(balanceOfWantBefore);
    }


    // it looks like this function transfers not just "want" tokens, but all tokens
    function prepareMigration(address _newStrategy) internal override {
        // want is transferred by the base contract's migrate function
        IERC20(crv3).transfer(_newStrategy, IERC20(crv3).balanceOf(address(this)));
        IERC20(y3Pool).transfer(_newStrategy, IERC20(y3Pool).balanceOf(address(this)));
    }

    // returns value of total 3pool
    function balanceOfPool() public view returns (uint256) {
        uint256 _balance = IERC20(crv3).balanceOf(address(this));
        uint256 ratio = ICurve(threePool).get_virtual_price();
        return (_balance).mul(ratio).div(1e18);
    }

    // returns value of total 3pool in vault
    function balanceOfStake() public view returns (uint256) {
        uint256 _balance = IERC20(y3Pool).balanceOf(address(this));
        uint256 ratio = Vault(y3Pool).getPricePerFullShare();
        return (_balance).mul(ratio).div(1e18);
    }

    // returns balance of dai
    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    function setSlip(uint _slip) external {
        require(msg.sender == strategist || msg.sender == governance(), "!sg");
        slip = _slip;
    }

    function setTrack() internal {
        ppsTrack = Vault(y3Pool).getPricePerFullShare().div(1e18);
    }

}

