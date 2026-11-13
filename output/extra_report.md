# Access control report for other provider contracts

Generated: 2026-11-13 22:45 UTC.

This report is an addition to `report.md`. It shows the current role holders of other contracts of each provider. These contracts are not stock tokens. Examples are the contracts that mint and burn the stock tokens. The provider file lists these contracts in `extras`.

The script did these steps for each contract:

1. The script read the role holders on chain at the snapshot block. For a contract with OpenZeppelin AccessControlEnumerable, the script called `getRoleMemberCount(role)` and `getRoleMember(role, index)`.
2. The script read the `RoleGranted` and `RoleRevoked` events from the block explorer. It kept only the current holders. It compared this list with the list from step 1.
3. The script read the code at each holder address. It set the type of each address.
4. For each contract, the script read the EIP-1967 storage slots. If the contract is an ERC-1967 proxy, the script read its implementation address. Then it read the type and the verification status of the implementation.

The snapshot block of each section is the same as the snapshot block of the provider in `report.md`.

Types of address:

- **EOA**: The address has no code.
- **EOA (EIP-7702)**: The address is an EOA with an EIP-7702 delegation. The "Note" column shows the delegate contract.
- **Contract (verified)**: The address has code. The explorer has the verified source code.
- **Contract (not verified)**: The address has code. The explorer does not have the verified source code.

"(not validated)" after an address means that the on-chain list and the event list do not agree. Examine these addresses manually.

The "Proxy contracts" table shows the role holders that are ERC-1967 proxies:

- **Proxy type**: "ERC-1967" means that the implementation is in the EIP-1967 implementation slot. "ERC-1967 beacon" means that the proxy gets the implementation from a beacon contract.
- **Admin or beacon**: The value of the EIP-1967 admin slot, or the beacon address. A dash means that the admin slot is empty. In this case, the upgrade function is usually in the implementation (UUPS).
- The contract name below an address comes from the block explorer.

Look at the "Role" column of the address and proxy tables. A contract list in parentheses shows that the address has the role only on those contracts. If there is no list, the address has the role on all contracts of the section.

A dash in the "Role holders by contract" table means that the contract has no holder for this role. Some roles do not exist on all contracts.

## Ondo Global Markets: minter contracts

GMTokenManager and GMIssuerManager hold MINTER_ROLE on all Ondo GM tokens. They mint GM tokens to users. The roles below control who can mint, sign prices, pause and change the configuration.

- Chain: Ethereum (chain ID 1).
- Snapshot block: 26409115.
- Validation: 13 of 13 role assignments agree with the RPC read at the snapshot block.

### Contracts

| Contract | Address | Description |
| --- | --- | --- |
| GMTokenManager | [0x2c158BC456e027b2AfFCCadF1BDBD9f5fC4c5C8c](https://etherscan.io/address/0x2c158BC456e027b2AfFCCadF1BDBD9f5fC4c5C8c) | Mints and redeems GM tokens for USDon or USDC. A key with ATTESTATION_SIGNER_ROLE signs each price quote. ADMIN_MINT_ROLE mints without a quote. Not a proxy. |
| GMIssuerManager | [0xec8bBB0c90c0B5F4D8240D0F7b49DA3b0aA41f4E](https://etherscan.io/address/0xec8bBB0c90c0B5F4D8240D0F7b49DA3b0aA41f4E) | Mints GM tokens for the Alpaca issuance path. SUBMITTER_ROLE sends mint requests that a key with ALPACA_SIGNER_ROLE signed. Users burn tokens to redeem. TransparentUpgradeableProxy. |

### Role hashes

To examine a role on the explorer, call `hasRole(role, account)` on the contract.

| Role | Hash (bytes32) |
| --- | --- |
| DEFAULT_ADMIN_ROLE | `0x0000000000000000000000000000000000000000000000000000000000000000` |
| CONFIGURER_ROLE | `0xf45c97b23e2beeefda80e1ce5cb3e234aa7b6888ad5cbabb75bfd654dd8e102d` |
| PAUSER_ROLE | `0x65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a` |
| UNPAUSER_ROLE | `0x427da25fe773164f88948d3e215c94b6554e2ed5e5f203a821c9f2f6131cf75a` |
| ATTESTATION_SIGNER_ROLE | `0x023d9737d781c665e5048e4dfd034f07fec540e8ecb2336b3d85a375b90a3a35` |
| ADMIN_MINT_ROLE | `0x507caaa5b2a5a027bc340a5334d9220583b7d60d846ee2aabc76e37d69a7253b` |
| SUBMITTER_ROLE | `0xe1a65d1a914580ff6931bc952f0fb26573e9282358a4458bceb9ccc6d923d041` |
| ALPACA_SIGNER_ROLE | `0x742e9758bb8517732aa7f53246de4ee8ca3fb2a828e6296a1bbbabf4ab7da5bb` |
| PRIVILEGED_USER_ROLE | `0xa46a8fde0b130ec3ec849eb5a766aa20ab2c49873033c007fb175faa5938b0a7` |

### Role holders by contract

| Role | GMTokenManager | GMIssuerManager |
| --- | --- | --- |
| DEFAULT_ADMIN_ROLE | 0x3715B2154d2FF4C5B027C7a1f734B53F27bc34f1 | 0x3715B2154d2FF4C5B027C7a1f734B53F27bc34f1 |
| CONFIGURER_ROLE | 0x71A4d411b5f7941Dee020417fca30413712f1646<br>0xD2746617c58b72254785BDb483e04f311c858d5f | 0x71A4d411b5f7941Dee020417fca30413712f1646 |
| PAUSER_ROLE | 0x2e55b738F5969Eea10fB67e326BEE5e2fA15A2CC | 0x2e55b738F5969Eea10fB67e326BEE5e2fA15A2CC |
| UNPAUSER_ROLE | 0x71A4d411b5f7941Dee020417fca30413712f1646 | 0x3715B2154d2FF4C5B027C7a1f734B53F27bc34f1 |
| ATTESTATION_SIGNER_ROLE | 0xff2D04f6002C10eba702aDafE2f43CAc5996C477 | — |
| ADMIN_MINT_ROLE | 0x71A4d411b5f7941Dee020417fca30413712f1646 | — |
| SUBMITTER_ROLE | — | 0xBef069828Ed464Cb6c41b60e608749E4fe76edaf |
| ALPACA_SIGNER_ROLE | — | 0x27b48877b4C056922F2659DD92C7D3ff2595E4dd |
| PRIVILEGED_USER_ROLE | — | — |

### Role holder addresses

| Address | Role | Type | Note |
| --- | --- | --- | --- |
| [0x3715B2154d2FF4C5B027C7a1f734B53F27bc34f1](https://etherscan.io/address/0x3715B2154d2FF4C5B027C7a1f734B53F27bc34f1) | DEFAULT_ADMIN_ROLE<br>UNPAUSER_ROLE (GMIssuerManager) | Contract (verified) | — |
| [0x71A4d411b5f7941Dee020417fca30413712f1646](https://etherscan.io/address/0x71A4d411b5f7941Dee020417fca30413712f1646) | CONFIGURER_ROLE<br>UNPAUSER_ROLE (GMTokenManager)<br>ADMIN_MINT_ROLE (GMTokenManager) | Contract (verified) | The explorer marks this contract as a proxy (type: proxy, implementation 0x41675C099F32341bf84BFc5382aF534df5C7461a). The tool does not support this proxy type. |
| [0xD2746617c58b72254785BDb483e04f311c858d5f](https://etherscan.io/address/0xD2746617c58b72254785BDb483e04f311c858d5f) | CONFIGURER_ROLE (GMTokenManager) | Contract (verified) | — |
| [0x2e55b738F5969Eea10fB67e326BEE5e2fA15A2CC](https://etherscan.io/address/0x2e55b738F5969Eea10fB67e326BEE5e2fA15A2CC) | PAUSER_ROLE | Contract (verified) | The explorer marks this contract as a proxy (type: proxy, implementation 0x3E5c63644E683549055b9Be8653de26E0B4CD36E). The tool does not support this proxy type. |
| [0xff2D04f6002C10eba702aDafE2f43CAc5996C477](https://etherscan.io/address/0xff2D04f6002C10eba702aDafE2f43CAc5996C477) | ATTESTATION_SIGNER_ROLE (GMTokenManager) | EOA | — |
| [0xBef069828Ed464Cb6c41b60e608749E4fe76edaf](https://etherscan.io/address/0xBef069828Ed464Cb6c41b60e608749E4fe76edaf) | SUBMITTER_ROLE (GMIssuerManager) | EOA | — |
| [0x27b48877b4C056922F2659DD92C7D3ff2595E4dd](https://etherscan.io/address/0x27b48877b4C056922F2659DD92C7D3ff2595E4dd) | ALPACA_SIGNER_ROLE (GMIssuerManager) | EOA | — |

### Proxy contracts

No role holder is a supported proxy.
