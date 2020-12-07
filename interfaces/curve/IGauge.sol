// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;

interface IGauge {
    function deposit(uint256) external;

    function balanceOf(address) external view returns (uint256);

    function withdraw(uint256) external;

    // claim the bonus tokens, e.g. mta
    function claim_rewards(address) external;


}
