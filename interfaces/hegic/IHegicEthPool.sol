// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

interface IHegicEthPool {
    function approve(address, uint256) external;

    function provide(uint256) external payable returns (uint256);

    function withdraw (uint256, uint256) external returns (uint256);

    function shareOf(address) external view returns (uint256);

    function availableBalance() external view returns (uint256);

    function totalBalance() external view returns (uint256);

    function totalSupply() external view returns (uint256);

    function lastProvideTimestamp(address) external view returns (uint256);

    function lockupPeriod() external view returns (uint256);

}
