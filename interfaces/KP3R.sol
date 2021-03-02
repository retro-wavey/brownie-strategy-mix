// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;

interface KP3RV1 {
    function jobs(address job) external view returns(bool);
    function addJob(address job) external;
    function addKPRCredit(address job, uint amount) external;
}