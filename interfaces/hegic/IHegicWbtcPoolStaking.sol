// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

interface IHegicWbtcPoolStaking {
    function stake(uint256) external;

    function withdraw(uint256) external;

    function getReward() external;

    function exit() external;

    function earned(address) external view returns(uint256);

    function balanceOf(address) external view returns (uint256);
}
