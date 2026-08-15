import json
import re
from pathlib import Path

from skinflow_api.application.scan.errors import NameIdIndexInvalid, NameIdIndexUnavailable

_NORMALIZE = re.compile(r"[^0-9a-z一-鿿]+")


class JsonNameIdResolver:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._mapping: dict[str, int] | None = None

    def resolve(self, market_hash_name: str) -> int | None:
        if self._mapping is None:
            self._mapping = self._load()
        direct = self._mapping.get(market_hash_name)
        if direct is not None:
            return direct
        target = _NORMALIZE.sub("", market_hash_name.lower())
        for name, item_nameid in self._mapping.items():
            if _NORMALIZE.sub("", name.lower()) == target:
                return item_nameid
        return None

    def _load(self) -> dict[str, int]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("nameid index must be an object")
            return {str(name): int(value) for name, value in raw.items()}
        except OSError as error:
            raise NameIdIndexUnavailable() from error
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise NameIdIndexInvalid() from error
