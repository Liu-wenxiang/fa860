from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(slots=True)
class ProtocolOptions:
    timeout: float = 1.0
    checksum: str | None = None


@dataclass(slots=True)
class CommandSpec:
    request: str
    append_checksum: bool = False
    read_size: int = 0


@dataclass(slots=True)
class ProtocolConfig:
    protocol: ProtocolOptions
    commands: dict[str, CommandSpec]


def load_protocol_config(path: str | Path) -> ProtocolConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    protocol = ProtocolOptions(**data.get("protocol", {}))
    commands = {
        name: CommandSpec(**spec)
        for name, spec in data.get("commands", {}).items()
    }
    return ProtocolConfig(protocol=protocol, commands=commands)
