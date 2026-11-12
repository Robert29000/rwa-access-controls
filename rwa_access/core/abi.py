"""Load contract ABIs from JSON files. Encode calls and decode logs.

An ABI file is a JSON list of ABI entries, or an object with an "abi" key
(Foundry / Hardhat artifact).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode

from rwa_access.core.models import Log
from rwa_access.evm import keccak_hex, to_checksum


class AbiError(ValueError):
    pass


def _canonical_type(param: dict) -> str:
    kind = param["type"]
    if kind.startswith("tuple"):
        inner = ",".join(_canonical_type(c) for c in param["components"])
        return f"({inner}){kind[len('tuple'):]}"
    return kind


def _to_abi_value(kind: str, value):
    """Accept hex strings for bytes types (config files hold hex text)."""
    if kind.startswith("bytes") and isinstance(value, str):
        return bytes.fromhex(value.removeprefix("0x"))
    return value


def _from_abi_value(kind: str, value):
    if kind == "address":
        return to_checksum(value)
    if kind.startswith("bytes") and isinstance(value, bytes):
        return "0x" + value.hex()
    return value


def _is_static(kind: str) -> bool:
    return kind not in ("string", "bytes") and not kind.endswith("]") and not kind.startswith("(")


@dataclass(frozen=True)
class Function:
    name: str
    signature: str
    selector: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]

    def encode(self, *args) -> str:
        if len(args) != len(self.input_types):
            raise AbiError(f"{self.signature} takes {len(self.input_types)} arguments, got {len(args)}")
        values = [_to_abi_value(t, v) for t, v in zip(self.input_types, args)]
        return self.selector + abi_encode(list(self.input_types), values).hex()

    def decode(self, result: str) -> tuple:
        raw = bytes.fromhex(result.removeprefix("0x"))
        values = abi_decode(list(self.output_types), raw)
        return tuple(_from_abi_value(t, v) for t, v in zip(self.output_types, values))


@dataclass(frozen=True)
class EventParam:
    name: str
    type: str
    indexed: bool


@dataclass(frozen=True)
class Event:
    name: str
    signature: str
    topic0: str
    inputs: tuple[EventParam, ...]

    def param(self, name: str) -> EventParam:
        for item in self.inputs:
            if item.name == name:
                return item
        names = ", ".join(i.name for i in self.inputs)
        raise AbiError(f"Event {self.signature} has no argument '{name}'. Arguments: {names}")

    def decode(self, log: Log) -> dict:
        """Decode a log into {argument name: value}.

        Indexed arguments come from topics[1..]. Other arguments come from data.
        An indexed dynamic value (string, bytes, array) is only a hash: it stays as hex.
        """
        out: dict = {}
        topics = iter(log.topics[1:])
        plain = [p for p in self.inputs if not p.indexed]
        for item in self.inputs:
            if item.indexed:
                topic = next(topics)
                if _is_static(item.type):
                    (value,) = abi_decode([item.type], bytes.fromhex(topic.removeprefix("0x")))
                    out[item.name] = _from_abi_value(item.type, value)
                else:
                    out[item.name] = topic
        if plain:
            values = abi_decode([p.type for p in plain], bytes.fromhex(log.data.removeprefix("0x")))
            for item, value in zip(plain, values):
                out[item.name] = _from_abi_value(item.type, value)
        return out


class Abi:
    def __init__(self, entries: list[dict], source: str = "<abi>"):
        self.source = source
        self.functions: dict[str, list[Function]] = {}
        self.events: dict[str, list[Event]] = {}
        for entry in entries:
            if entry.get("type") == "function":
                types = tuple(_canonical_type(p) for p in entry.get("inputs", []))
                sig = f"{entry['name']}({','.join(types)})"
                fn = Function(
                    entry["name"], sig, keccak_hex(sig)[:10], types,
                    tuple(_canonical_type(p) for p in entry.get("outputs", [])),
                )
                self.functions.setdefault(fn.name, []).append(fn)
            elif entry.get("type") == "event":
                params = tuple(
                    EventParam(p["name"], _canonical_type(p), bool(p.get("indexed")))
                    for p in entry.get("inputs", [])
                )
                sig = f"{entry['name']}({','.join(p.type for p in params)})"
                self.events.setdefault(entry["name"], []).append(
                    Event(entry["name"], sig, keccak_hex(sig), params)
                )

    @staticmethod
    def _pick(kind: str, items: dict[str, list], name: str, source: str):
        """Find by name, or by full signature for overloaded names."""
        key = name.split("(")[0]
        candidates = items.get(key, [])
        if "(" in name:
            candidates = [c for c in candidates if c.signature == name.replace(" ", "")]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise AbiError(f"{source}: no {kind} '{name}'")
        options = ", ".join(c.signature for c in candidates)
        raise AbiError(f"{source}: {kind} '{name}' is overloaded. Use the full signature: {options}")

    def function(self, name: str) -> Function:
        return self._pick("function", self.functions, name, self.source)

    def event(self, name: str) -> Event:
        return self._pick("event", self.events, name, self.source)


class AbiStore:
    """Load ABI files from one directory, with a cache.

    `aliases` maps a short name (from a provider config) to a file path.
    """

    def __init__(self, root: Path, aliases: dict[str, str] | None = None, _cache=None):
        self.root = root
        self.aliases = aliases or {}
        self._cache: dict[Path, Abi] = {} if _cache is None else _cache

    def with_aliases(self, aliases: dict[str, str]) -> "AbiStore":
        return AbiStore(self.root, aliases, self._cache)

    def get(self, ref: str) -> Abi:
        path = (self.root / self.aliases.get(ref, ref)).resolve()
        if path not in self._cache:
            if not path.is_file():
                raise AbiError(f"ABI file not found: {path} (reference '{ref}')")
            data = json.loads(path.read_text())
            entries = data["abi"] if isinstance(data, dict) else data
            self._cache[path] = Abi(entries, str(path.relative_to(self.root.resolve())))
        return self._cache[path]
