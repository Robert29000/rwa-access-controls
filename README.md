# RWA access controls

This tool collects the current role holders of tokenized stocks. It checks each holder on chain and writes the results to CSV and Markdown files.

## Scope

| Provider | Chain | Stocks | Role model |
|---|---|---|---|
| Robinhood Stocks | Robinhood Chain (chain ID 4663) | NVDA, MSFT, TSLA, GOOGL, AAPL, SPCX (SpaceX), META | OpenZeppelin AccessControl in an external registry |
| xStocks | Ethereum (chain ID 1) | NVDAx, MSFTx, TSLAx, GOOGLx, AAPLx, SPCXx (SpaceX), METAx | One address variable for each role |

### Robinhood Stocks

- Each token is a BeaconProxy for the `Stock` contract.
- `Stock` sends each role check to the registry in `ACCESS_CONTROLLED_REGISTRY()`. The check is `hasRole(role, sender)`.
- The tool reads the registry address for each token. Tokens with the same registry share the same role holders.
- The registry has no enumeration. The tool replays the `RoleGranted` and `RoleRevoked` events to find the current holders.
- The tool reports the 13 roles from `Roles.sol`.

### xStocks

- Each token is a TransparentUpgradeableProxy for `BackedAutoFeeTokenImplementation`.
- The token roles are `owner`, `minter`, `burner`, `pauser` and `multiplierUpdater`.
- The tool also reports `proxyAdmin` (the EIP-1967 admin slot) and `proxyAdminOwner`. The owner of the ProxyAdmin can upgrade the token.

## How the tool works

For each provider, the tool does these steps:

1. It reads the latest block number. All later reads use this snapshot block.
2. It reads the role events from the block explorer and keeps only the current holders.
3. It reads each role on chain with an RPC call at the snapshot block. It compares this value with the value from the events.
4. It runs the token checks from the provider config.
5. It reads the code at each holder address with `eth_getCode` and sets the address type:
   - No code: `EOA`.
   - Exactly `0xef0100` + 20-byte address: `EOA (EIP-7702)`. The delegate address goes in the note.
   - Other code: `Contract`. The tool asks the explorer for the verification status of the source code.
6. It writes the output files.

### Data sources

| Source | Use | Free-tier limit |
|---|---|---|
| Etherscan API V2 | Ethereum logs, verified status | 3 requests/s |
| Blockscout PRO API (`api.blockscout.com/4663`) | Robinhood Chain logs, verified status | 5 requests/s |
| dRPC (`lb.drpc.live`) | `eth_call`, `eth_getCode`, `eth_getStorageAt` | 25 requests/s |

The tool keeps a fixed pace for each service. It tries a request again when the service sends a rate-limit error.

Do not use `robinhoodchain.blockscout.com` for API calls. A Cloudflare bot check blocks scripts on that host.

## Setup

Python 3.11 or later is necessary.

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env   # Then set the API keys in .env
```

`.env` contains these keys:

```
ETHERSCAN_API_KEY=...
BLOCKSCOUT_API_KEY=...
DRPC_API_KEY=...
```

## Run

```sh
.venv/bin/python -m rwa_access                        # All providers
.venv/bin/python -m rwa_access --providers xstocks    # One provider
.venv/bin/python -m rwa_access --out reports/ -v      # Other output directory, debug log
.venv/bin/python -m rwa_access --config my-config/ --abis my-abis/
```

A provider name is the file name of its config, without `.yaml`.

## Output

The tool writes these files to `output/`:

| File | Content |
|---|---|
| `role_assignments.csv` | One row for each (stock, role, holder). It includes the last change block and transaction, the address type, and the validation result. |
| `addresses.csv` | One row for each holder address, with its type and roles. |
| `report.md` | For each provider: a token list, a role × stock table, and an address table. |

`validated=True` means that the on-chain value agrees with the value from the events. If `validated=False`, the `note` column gives the on-chain value. Examine these rows manually.

## Configuration

```
config/
  chains.yaml               API services and chains
  providers/
    robinhood.yaml          One file for each provider
    xstocks.yaml
abis/
  openzeppelin/             Standard interfaces (AccessControl)
  robinhood/                Stock, AccessControlsRegistry
  backed/                   BackedAutoFeeTokenImplementation, BackedTokenProxy, ProxyAdmin
```

### Chains

`config/chains.yaml` has two sections:

- `services`: the URL, the environment variable for the API key, and the pace for each API service.
- `chains`: the chain ID, the RPC service and network, the explorer service, and the explorer address URL for the report.

### ABIs

Each file in `abis/` is a JSON ABI. The tool also accepts a Foundry or Hardhat artifact with an `abi` key. The tool calculates the selectors and event topics from the ABI. It also decodes the logs and return values with the ABI.

Provider configs refer to an ABI by its path in `abis/`, or by a short name from the `abis` section of the provider file. More than one provider can use the same ABI file.

If two functions or two events have the same name, use the full signature, for example `transfer(address,uint256)`.

### Provider file

All provider files have these keys:

| Key | Content |
|---|---|
| `name` | Name in the report. |
| `chain` | Chain key from `chains.yaml`. |
| `framework` | Role model: `access_control`, `single_address_roles`, or `package.module:ClassName` for a custom class. |
| `abis` | Optional. Short names for ABI files. |
| `tokens` | List of `{stock, symbol, address, start_block}`. `start_block` is optional. The log scan starts at this block. |
| `token_checks` | Optional. Values to read from each token and compare. See below. |

#### `framework: access_control`

Use this framework for OpenZeppelin AccessControl. List only the roles that you want to report.

```yaml
access_control:
  abi: openzeppelin/AccessControl.json          # Default. Needs RoleGranted, RoleRevoked, hasRole.
  registry: {abi: stock, function: ACCESS_CONTROLLED_REGISTRY}   # Optional. Default: the token itself.
  start_blocks: {"0xRegistry...": 7662}         # Optional
  roles:
    - DEFAULT_ADMIN_ROLE                        # Hash 0x00
    - MINTER_ROLE                               # Hash keccak256("MINTER_ROLE")
    - {name: CUSTOM_ROLE, hash: "0x1234..."}    # Explicit hash
```

The tool does not report holders of roles that are not in the list. The report gives a note with the hashes of these roles.

#### `framework: single_address_roles`

Use this framework when each role is one address variable with a setter event.

```yaml
roles:
  - name: minter
    event: {abi: token, name: NewMinter, arg: newMinter}   # Setter event and its address argument
    read: {abi: token, function: minter}                   # Reader for validation
  - name: proxyAdmin
    event: {abi: proxy, name: AdminChanged, arg: newAdmin}
    read: {storage_slot: eip1967.admin}
  - name: proxyAdminOwner
    source: proxyAdmin      # Use the address of an earlier role, not the token
    start_block: 0
    event: {abi: proxy_admin, name: OwnershipTransferred, arg: newOwner}
    read: {abi: proxy_admin, function: owner}
```

The newest event gives the current holder. The argument can be indexed or not indexed.

#### Readers

A reader gets one value from a contract at the snapshot block:

- `{abi: <ABI>, function: <name>, args: [...]}`: an `eth_call`. The tool uses the first return value.
- `{storage_slot: <slot>}`: an `eth_getStorageAt`. The tool reads the value as an address. The slot is a hex value or one of these names: `eip1967.implementation`, `eip1967.admin`, `eip1967.beacon`.

#### Token checks

```yaml
token_checks:
  - name: beacon is the role registry
    read: {storage_slot: eip1967.beacon}
    expect: registry
```

`expect` is an address, or a name that the framework gives for each token:

- `access_control`: `registry`.
- `single_address_roles`: the name of a role.

If a check fails, the tool adds a note to the report and to the rows of that token.

## Add a provider

1. Put the ABIs of the contracts in `abis/<project>/`. You can get a verified ABI from the explorer.
2. Make `config/providers/<name>.yaml`. Use one of the frameworks above.
3. Pin the token addresses. Explorer search can show copy tokens.
4. If the provider uses a new chain, add the chain to `config/chains.yaml`.
5. Run `.venv/bin/pytest -q`. The config test loads all provider files and finds errors in ABI names and arguments.
6. Run `.venv/bin/python -m rwa_access --providers <name>`.

If no framework agrees with the role model, write a subclass of `StockProvider` in `rwa_access/providers/`. Write `role_names()`, `collect()` and `validate()`. Then set `framework: rwa_access.providers.<module>:<ClassName>` in the provider file.

## Tests

```sh
.venv/bin/pytest -q
```

The tests cover these items: the event replay, the address classification, the Markdown tables, and the loading of the shipped configs and ABIs. They do not use the network.

## Project layout

```
rwa_access/
  config.py            chains.yaml loader, .env keys, client set-up
  http.py              Paced HTTP session with retries
  evm.py               Keccak and address format
  clients/             RPC, Etherscan and Blockscout clients
  core/
    abi.py             ABI loader: selectors, topics, call encoding, log decoding
    reads.py           Readers (eth_call, storage slot)
    replay.py          Event replay
    classify.py        Address classification
    models.py          Data models
  providers/
    __init__.py        Provider loader and framework list
    base.py            StockProvider, provider config, token checks
    access_control.py  Framework: access_control
    storage_roles.py   Framework: single_address_roles
  output/              CSV and Markdown writers
config/                Chains and providers (YAML)
abis/                  Contract ABIs (JSON)
tests/
```
