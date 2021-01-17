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


contract StrategyWBTCsBTCPool is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    address public wbtc;
    address public sbtcPool;
    address public ysBTC;
    address public crvsBTC;
    string public constant override name = "StrategyWBTCsBTCPool";

    // adding protection against slippage attacks
    uint constant public DENOMINATOR = 10000;
    uint public slip = 100;

    constructor(
        address _vault,
        address _wbtc,
        address _sbtcPool,
        address _ysBTC,
        address _crvsBTC
    ) public BaseStrategy(_vault) {
        wbtc = _wbtc;
        sbtcPool = _sbtcPool;
        ysBTC = _ysBTC;
        crvsBTC = _crvsBTC;

        IERC20(wbtc).safeApprove(sbtcPool, uint256(-1));
        IERC20(crvsBTC).safeApprove(ysBTC, uint256(-1));
    }

    function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](2);
        // dai (aka want) is already protected by default
        protected[0] = ysBTC;
        protected[1] = crvsBTC;
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

        // harvest() does not require any action on behalf of this strategy, so profit each harvest is zero.
        uint256 balanceOfWantBefore = balanceOfWant();
        _profit = balanceOfWant().sub(balanceOfWantBefore);

        //harvest() also does not generate losses. Funds stay in yvSBTC vault if not performing debt repayment.
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
            uint256 _availableFunds = IERC20(wbtc).balanceOf(address(this));
            uint256 v = _availableFunds.mul(1e18).div(ICurve(sbtcPool).get_virtual_price());
            ICurve(sbtcPool).add_liquidity([0,_availableFunds,0], v.mul(DENOMINATOR.sub(slip)).div(DENOMINATOR));
            Vault(ysBTC).depositAll();
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
        uint256 balanceOfWantBefore = balanceOfWant();
        uint256 totalValueBefore = estimatedTotalAssets();
        Vault(ysBTC).withdrawAll();
        uint256 sbtcPoolBalance = IERC20(crvsBTC).balanceOf(address(this));
        ICurve(sbtcPool).remove_liquidity_one_coin(sbtcPoolBalance, 1, 0);
        _profit = balanceOfWant().sub(balanceOfWantBefore);
        _loss = totalValueBefore.sub(estimatedTotalAssets());
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
        uint256 _sbtcPoolAmount = (_amount).mul(1e18).div(ICurve(sbtcPool).get_virtual_price());
        uint256 ysBTCAmount = (_sbtcPoolAmount).mul(1e18).div(Vault(ysBTC).getPricePerFullShare());
        Vault(ysBTC).withdraw(ysBTCAmount);
        uint256 sbtcPoolBalance = IERC20(crvsBTC).balanceOf(address(this));
        uint256 v = sbtcPoolBalance.mul(1e18).div(ICurve(sbtcPool).get_virtual_price());
        ICurve(sbtcPool).remove_liquidity_one_coin(sbtcPoolBalance, 1, v);
        uint256 balanceAfter = balanceOfWant();
        return balanceAfter.sub(balanceOfWantBefore);
    }


    // it looks like this function transfers not just "want" tokens, but all tokens
    function prepareMigration(address _newStrategy) internal override {
        // want is transferred by the base contract's migrate function
        IERC20(crvsBTC).transfer(_newStrategy, IERC20(crvsBTC).balanceOf(address(this)));
        IERC20(ysBTC).transfer(_newStrategy, IERC20(ysBTC).balanceOf(address(this)));
    }

    // returns value of total 3pool
    function balanceOfPool() internal view returns (uint256) {
        uint256 _balance = IERC20(crvsBTC).balanceOf(address(this));
        uint256 ratio = ICurve(sbtcPool).get_virtual_price();
        return (_balance).mul(ratio);
    }

    // returns value of total 3pool in vault
    function balanceOfStake() internal view returns (uint256) {
        uint256 _balance = IERC20(ysBTC).balanceOf(address(this));
        uint256 ratio = Vault(ysBTC).getPricePerFullShare();
        return (_balance).mul(ratio);
    }

    // returns balance of wbtc
    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    function setSlip(uint _slip) external {
        require(msg.sender == strategist || msg.sender == governance(), "!sg");
        slip = _slip;
    }

}

