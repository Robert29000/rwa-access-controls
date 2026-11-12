"""Load config/chains.yaml and build the clients for each chain. API keys come from .env."""

import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import yaml
from dotenv import load_dotenv

from rwa_access.clients.blockscout import BlockscoutExplorer
from rwa_access.clients.etherscan import EtherscanExplorer
from rwa_access.clients.explorer import Explorer
from rwa_access.clients.rpc import RpcClient
from rwa_access.core.abi import AbiStore
from rwa_access.core.classify import AddressClassifier
from rwa_access.core.proxy import default_detectors
from rwa_access.http import RateLimitedSession

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = ROOT / "config"
DEFAULT_ABI_DIR = ROOT / "abis"

EXPLORERS: dict[str, type[Explorer]] = {
    "etherscan": EtherscanExplorer,
    "blockscout": BlockscoutExplorer,
}


class ConfigError(ValueError):
    pass


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the top level must be a mapping")
    return data


def require_env(name: str) -> str:
    load_dotenv()
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing {name}. Set it in .env (see .env.example).")
    return value


@dataclass(frozen=True)
class ServiceConfig:
    key: str
    type: str
    url: str
    api_key_env: str
    min_interval: float


@dataclass(frozen=True)
class ChainConfig:
    key: str
    name: str
    chain_id: int
    rpc_service: ServiceConfig
    rpc_network: str
    explorer_service: ServiceConfig
    address_url: str

    def link(self, address: str) -> str:
        return self.address_url.format(address=address)


def load_chains(path: Path) -> dict[str, ChainConfig]:
    data = load_yaml(path)
    try:
        services = {
            key: ServiceConfig(
                key=key,
                type=raw.get("type", key),
                url=raw["url"],
                api_key_env=raw["api_key_env"],
                min_interval=float(raw.get("min_interval", 0.2)),
            )
            for key, raw in data["services"].items()
        }
        chains = {}
        for key, raw in data["chains"].items():
            chains[key] = ChainConfig(
                key=key,
                name=raw["name"],
                chain_id=int(raw["chain_id"]),
                rpc_service=services[raw["rpc"]["service"]],
                rpc_network=raw["rpc"]["network"],
                explorer_service=services[raw["explorer"]["service"]],
                address_url=raw["address_url"],
            )
    except KeyError as exc:
        raise ConfigError(f"{path}: missing or unknown key {exc}") from exc
    return chains


# One session per service, so the pace limit applies across all chains.
_SESSIONS: dict[str, RateLimitedSession] = {}


def _session(service: ServiceConfig) -> RateLimitedSession:
    if service.key not in _SESSIONS:
        _SESSIONS[service.key] = RateLimitedSession(service.min_interval)
    return _SESSIONS[service.key]


class ChainContext:
    """RPC, explorer and address classifier for one chain. Clients are made on first use."""

    def __init__(self, chain: ChainConfig, abis: AbiStore | None = None):
        self.chain = chain
        self.abis = abis or AbiStore(DEFAULT_ABI_DIR)  # For the proxy detectors

    @cached_property
    def rpc(self) -> RpcClient:
        service = self.chain.rpc_service
        url = service.url.format(
            network=self.chain.rpc_network,
            chain_id=self.chain.chain_id,
            api_key=require_env(service.api_key_env),
        )
        return RpcClient(url, _session(service))

    @cached_property
    def explorer(self) -> Explorer:
        service = self.chain.explorer_service
        if service.type not in EXPLORERS:
            raise ConfigError(f"Unknown explorer type '{service.type}'. Known: {', '.join(EXPLORERS)}")
        base_url = service.url.format(chain_id=self.chain.chain_id)
        return EXPLORERS[service.type](
            base_url, self.chain.chain_id, require_env(service.api_key_env), _session(service)
        )

    @cached_property
    def classifier(self) -> AddressClassifier:
        return AddressClassifier(self.rpc, self.explorer, default_detectors(self.abis))
