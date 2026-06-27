#!/usr/bin/env python3
"""Binary-size gate for performance-first Chromium Rust artifacts."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


@dataclass(frozen=True)
class SizeViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class ArtifactMeasurement:
    path: Path
    size_bytes: int

    def to_json(self) -> dict[str, Any]:
        return {"path": str(self.path), "size_bytes": self.size_bytes}


@dataclass(frozen=True)
class ArtifactBudget:
    path: Path
    max_bytes: int | None = None
    baseline_bytes: int | None = None
    max_growth_bytes: int | None = None

    def validate(self) -> list[SizeViolation]:
        violations: list[SizeViolation] = []
        for label, value in (
            ("max_bytes", self.max_bytes),
            ("baseline_bytes", self.baseline_bytes),
            ("max_growth_bytes", self.max_growth_bytes),
        ):
            if value is not None and value < 0:
                violations.append(
                    SizeViolation("invalid budget", f"{self.path}: {label} must be >= 0")
                )
        return violations


class BudgetFile:
    @staticmethod
    def load(path: Path) -> list[ArtifactBudget]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"could not read budget file {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON budget file {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("budget file root must be an object")
        raw_artifacts = payload.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise ValueError("budget file must contain an artifacts array")

        budgets: list[ArtifactBudget] = []
        for index, item in enumerate(raw_artifacts):
            if not isinstance(item, dict):
                raise ValueError(f"artifacts[{index}] must be an object")
            raw_path = item.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                raise ValueError(f"artifacts[{index}].path must be a non-empty string")
            budgets.append(
                ArtifactBudget(
                    path=Path(raw_path),
                    max_bytes=_optional_int(item, "max_bytes", index),
                    baseline_bytes=_optional_int(item, "baseline_bytes", index),
                    max_growth_bytes=_optional_int(item, "max_growth_bytes", index),
                )
            )
        return budgets


class ArtifactSizeGate:
    def measure(self, paths: Sequence[Path]) -> tuple[list[ArtifactMeasurement], list[SizeViolation]]:
        measurements: list[ArtifactMeasurement] = []
        violations: list[SizeViolation] = []
        for path in paths:
            if not path.exists():
                violations.append(SizeViolation("missing artifact", str(path)))
                continue
            if not path.is_file():
                violations.append(SizeViolation("invalid artifact", f"{path} is not a file"))
                continue
            measurements.append(ArtifactMeasurement(path=path, size_bytes=path.stat().st_size))
        return measurements, violations

    def check_budgets(
        self,
        measurements: Sequence[ArtifactMeasurement],
        budgets: Sequence[ArtifactBudget],
        max_total_bytes: int | None,
    ) -> list[SizeViolation]:
        violations: list[SizeViolation] = []
        measurement_by_path = {measurement.path: measurement for measurement in measurements}
        total_size = sum(measurement.size_bytes for measurement in measurements)

        if max_total_bytes is not None and total_size > max_total_bytes:
            violations.append(
                SizeViolation(
                    "total size exceeded",
                    f"{total_size} bytes > {max_total_bytes} bytes",
                )
            )

        for budget in budgets:
            violations.extend(budget.validate())
            measurement = measurement_by_path.get(budget.path)
            if measurement is None:
                violations.append(SizeViolation("missing budget artifact", str(budget.path)))
                continue
            violations.extend(self._check_one(measurement, budget))
        return violations

    @staticmethod
    def _check_one(
        measurement: ArtifactMeasurement, budget: ArtifactBudget
    ) -> list[SizeViolation]:
        violations: list[SizeViolation] = []
        if budget.max_bytes is not None and measurement.size_bytes > budget.max_bytes:
            violations.append(
                SizeViolation(
                    "artifact size exceeded",
                    f"{measurement.path}: {measurement.size_bytes} bytes > {budget.max_bytes} bytes",
                )
            )
        if budget.baseline_bytes is not None and budget.max_growth_bytes is not None:
            growth = measurement.size_bytes - budget.baseline_bytes
            if growth > budget.max_growth_bytes:
                violations.append(
                    SizeViolation(
                        "artifact growth exceeded",
                        f"{measurement.path}: +{growth} bytes > +{budget.max_growth_bytes} bytes",
                    )
                )
        return violations


class CargoLockGate:
    def count_registry_packages(self, lockfile: Path) -> int:
        if not lockfile.exists():
            raise ValueError(f"lockfile does not exist: {lockfile}")
        count = 0
        for line in lockfile.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith('source = "registry+'):
                count += 1
        return count

    def check(self, lockfile: Path, max_registry_packages: int | None) -> tuple[int | None, list[SizeViolation]]:
        if max_registry_packages is None:
            return None, []
        if max_registry_packages < 0:
            return None, [SizeViolation("invalid dependency budget", "max registry packages must be >= 0")]
        count = self.count_registry_packages(lockfile)
        if count > max_registry_packages:
            return count, [
                SizeViolation(
                    "registry dependency budget exceeded",
                    f"{count} registry packages > {max_registry_packages}",
                )
            ]
        return count, []


class CargoMetadataGate:
    def count_registry_packages(
        self,
        package: str,
        no_default_features: bool,
        features: Sequence[str],
    ) -> int:
        command = ["cargo", "metadata", "--format-version=1"]
        if no_default_features:
            command.append("--no-default-features")
        if features:
            command.extend(["--features", ",".join(features)])

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError(f"could not run cargo metadata: {exc}") from exc

        payload = json.loads(completed.stdout)
        packages_by_id = {item["id"]: item for item in payload.get("packages", [])}
        resolve = payload.get("resolve")
        if not isinstance(resolve, dict):
            raise ValueError("cargo metadata did not include a resolve graph")

        root_id = self._find_package_id(packages_by_id, package)
        nodes = resolve.get("nodes", [])
        deps_by_id = {
            node["id"]: [dep["pkg"] for dep in node.get("deps", [])]
            for node in nodes
            if isinstance(node, dict)
        }

        seen: set[str] = set()
        stack = list(deps_by_id.get(root_id, []))
        while stack:
            package_id = stack.pop()
            if package_id in seen:
                continue
            seen.add(package_id)
            stack.extend(deps_by_id.get(package_id, []))

        count = 0
        for package_id in seen:
            package_info = packages_by_id.get(package_id, {})
            source = package_info.get("source")
            if isinstance(source, str) and source.startswith("registry+"):
                count += 1
        return count

    @staticmethod
    def _find_package_id(packages_by_id: dict[str, dict[str, Any]], package: str) -> str:
        matches = [
            package_id
            for package_id, package_info in packages_by_id.items()
            if package_info.get("name") == package
        ]
        if len(matches) != 1:
            raise ValueError(f"expected one package named {package}, found {len(matches)}")
        return matches[0]

    def check(
        self,
        package: str,
        no_default_features: bool,
        features: Sequence[str],
        max_registry_packages: int | None,
    ) -> tuple[int | None, list[SizeViolation]]:
        if max_registry_packages is None:
            return None, []
        if max_registry_packages < 0:
            return None, [SizeViolation("invalid dependency budget", "max registry packages must be >= 0")]
        count = self.count_registry_packages(package, no_default_features, features)
        if count > max_registry_packages:
            return count, [
                SizeViolation(
                    "registry dependency budget exceeded",
                    f"{count} registry packages > {max_registry_packages}",
                )
            ]
        return count, []


def _optional_int(item: dict[str, Any], key: str, index: int) -> int | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"artifacts[{index}].{key} must be an integer")
    return value


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", default=[], type=Path)
    parser.add_argument("--budget-file", type=Path)
    parser.add_argument("--max-total-bytes", type=int)
    parser.add_argument("--lockfile", type=Path, default=Path("Cargo.lock"))
    parser.add_argument("--package")
    parser.add_argument("--no-default-features", action="store_true")
    parser.add_argument("--features", action="append", default=[])
    parser.add_argument("--max-registry-packages", type=int)
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args(argv)


def _write_json_report(
    path: Path,
    measurements: Sequence[ArtifactMeasurement],
    registry_package_count: int | None,
    violations: Sequence[SizeViolation],
) -> None:
    report = {
        "artifacts": [measurement.to_json() for measurement in measurements],
        "registry_package_count": registry_package_count,
        "violations": [violation.render() for violation in violations],
        "ok": not violations,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    budgets = BudgetFile.load(args.budget_file) if args.budget_file else []
    artifact_paths = list(args.artifact)
    for budget in budgets:
        if budget.path not in artifact_paths:
            artifact_paths.append(budget.path)

    size_gate = ArtifactSizeGate()
    measurements, violations = size_gate.measure(artifact_paths)
    violations.extend(size_gate.check_budgets(measurements, budgets, args.max_total_bytes))

    if args.package:
        registry_package_count, dependency_violations = CargoMetadataGate().check(
            args.package,
            args.no_default_features,
            args.features,
            args.max_registry_packages,
        )
    else:
        registry_package_count, dependency_violations = CargoLockGate().check(
            args.lockfile, args.max_registry_packages
        )
    violations.extend(dependency_violations)

    if args.json_output:
        _write_json_report(args.json_output, measurements, registry_package_count, violations)

    for measurement in measurements:
        print(f"{measurement.path}: {measurement.size_bytes} bytes")
    if registry_package_count is not None:
        print(f"registry packages: {registry_package_count}")
    for violation in violations:
        print(violation.render(), file=sys.stderr)

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
