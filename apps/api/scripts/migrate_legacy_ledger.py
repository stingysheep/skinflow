import argparse
import json

from skinflow_api.infrastructure.database.ledger import migrate_legacy_ledger


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate a legacy Skinflow ledger once")
    parser.add_argument("source", help="legacy ledger.db path")
    parser.add_argument("target", help="new Skinflow SQLite path")
    parser.add_argument("--version", default="v1")
    args = parser.parse_args()
    report = migrate_legacy_ledger(args.source, args.target, args.version)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
