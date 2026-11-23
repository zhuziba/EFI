#!/usr/bin/env python3
"""Update EFI binaries from their upstream GitHub releases."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
EFI_ROOT = ROOT / "EFI"
OC_ROOT = EFI_ROOT / "OC"
CONFIG_PATH = OC_ROOT / "config.plist"
VERSIONS_PATH = ROOT / "scripts" / "efi-versions.json"
API_ROOT = "https://api.github.com"
USER_AGENT = "EFI-driver-update-workflow"

KEXT_PACKAGES = (
    ("acidanthera/Lilu", "Lilu-", "-RELEASE.zip", ("Lilu.kext",)),
    (
        "acidanthera/WhateverGreen",
        "WhateverGreen-",
        "-RELEASE.zip",
        ("WhateverGreen.kext",),
    ),
    (
        "acidanthera/VirtualSMC",
        "VirtualSMC-",
        "-RELEASE.zip",
        ("VirtualSMC.kext", "SMCProcessor.kext", "SMCSuperIO.kext"),
    ),
    ("acidanthera/AppleALC", "AppleALC-", "-RELEASE.zip", ("AppleALC.kext",)),
    ("acidanthera/NVMeFix", "NVMeFix-", "-RELEASE.zip", ("NVMeFix.kext",)),
    (
        "acidanthera/RestrictEvents",
        "RestrictEvents-",
        "-RELEASE.zip",
        ("RestrictEvents.kext",),
    ),
    (
        "acidanthera/BrcmPatchRAM",
        "BrcmPatchRAM-",
        "-RELEASE.zip",
        ("BlueToolFixup.kext",),
    ),
    (
        "OpenIntelWireless/IntelBluetoothFirmware",
        "IntelBluetooth-",
        ".zip",
        ("IntelBluetoothFirmware.kext",),
    ),
    (
        "Mieze/RTL8111_driver_for_OS_X",
        "RealtekRTL8111-",
        ".zip",
        ("RealtekRTL8111.kext",),
    ),
    ("USBToolBox/kext", "USBToolBox-", "-RELEASE.zip", ("USBToolBox.kext",)),
)


class UpdateError(RuntimeError):
    pass


def request_bytes(url: str, *, api: bool = False) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if api and token:
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise UpdateError(f"Unable to download {url}: {error}") from error


def get_latest_release(repository: str) -> dict:
    data = request_bytes(f"{API_ROOT}/repos/{repository}/releases/latest", api=True)
    try:
        release = json.loads(data)
    except json.JSONDecodeError as error:
        raise UpdateError(f"GitHub returned invalid release data for {repository}") from error
    if not isinstance(release, dict) or not isinstance(release.get("assets"), list):
        raise UpdateError(f"No latest release found for {repository}")
    return release


def get_asset(release: dict, prefix: str, suffix: str) -> dict:
    assets = [
        asset
        for asset in release["assets"]
        if asset["name"].startswith(prefix) and asset["name"].endswith(suffix)
    ]
    if len(assets) != 1:
        raise UpdateError(
            f"Expected one asset matching {prefix}*{suffix}; "
            f"found {[asset['name'] for asset in assets]}"
        )
    return assets[0]


def version_key(value: str) -> tuple:
    match = re.fullmatch(
        r"[vV]?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?",
        value.strip(),
    )
    if not match:
        raise UpdateError(f"Unsupported version string: {value!r}")
    numbers = tuple(int(part) for part in match.group(1).split("."))
    prerelease = match.group(2)
    if prerelease is None:
        return numbers, (1,)

    identifiers = []
    for identifier in prerelease.split("."):
        identifiers.append((0, int(identifier)) if identifier.isdigit() else (1, identifier))
    return numbers, (0, *identifiers)


def is_newer(candidate: str, current: str) -> bool:
    candidate_numbers, candidate_pre = version_key(candidate)
    current_numbers, current_pre = version_key(current)
    width = max(len(candidate_numbers), len(current_numbers))
    candidate_numbers += (0,) * (width - len(candidate_numbers))
    current_numbers += (0,) * (width - len(current_numbers))
    return (candidate_numbers, candidate_pre) > (current_numbers, current_pre)


def download_asset(asset: dict, destination: Path) -> None:
    data = request_bytes(asset["browser_download_url"])
    destination.write_bytes(data)


def safe_extract(archive_path: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                member = PurePosixPath(entry.filename)
                mode = entry.external_attr >> 16
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or "\\" in entry.filename
                    or stat.S_ISLNK(mode)
                ):
                    raise UpdateError(f"Unsafe path in release archive: {entry.filename}")
            archive.extractall(destination)
    except zipfile.BadZipFile as error:
        raise UpdateError(f"Invalid release archive: {archive_path.name}") from error


def find_bundle(root: Path, bundle_name: str) -> Path:
    matches = [
        path
        for path in root.rglob(bundle_name)
        if path.is_dir() and (path / "Contents" / "Info.plist").is_file()
    ]
    release_matches = [path for path in matches if "Release" in path.parts]
    if release_matches:
        matches = release_matches
    if len(matches) != 1:
        raise UpdateError(
            f"Expected one {bundle_name} in release archive; found "
            f"{[str(path.relative_to(root)) for path in matches]}"
        )
    return matches[0]


def bundle_version(bundle: Path) -> str:
    import plistlib

    try:
        with (bundle / "Contents" / "Info.plist").open("rb") as file:
            info = plistlib.load(file)
    except (OSError, ValueError) as error:
        raise UpdateError(f"Invalid Info.plist in {bundle}") from error
    version = info.get("CFBundleVersion") or info.get("CFBundleShortVersionString")
    if not isinstance(version, str):
        raise UpdateError(f"No bundle version found in {bundle}")
    return version


def bundle_config_entries(config: dict) -> dict[str, dict]:
    return {
        entry["BundlePath"]: entry
        for entry in config["Kernel"]["Add"]
        if entry.get("Enabled") is True
    }


def validate_bundle(bundle: Path, entry: dict) -> None:
    if not (bundle / "Contents" / "Info.plist").is_file():
        raise UpdateError(f"Missing Contents/Info.plist in {bundle}")
    executable = entry.get("ExecutablePath", "")
    if executable and not (bundle / PurePosixPath(executable)).is_file():
        raise UpdateError(f"Missing configured executable {executable} in {bundle}")


def stage_kext_updates(
    temporary_root: Path, config: dict, candidates: dict[Path, Path]
) -> list[str]:
    entries = bundle_config_entries(config)
    updated = []

    for index, (repository, prefix, suffix, bundle_names) in enumerate(KEXT_PACKAGES):
        release = get_latest_release(repository)
        asset = get_asset(release, prefix, suffix)
        archive_path = temporary_root / f"kext-{index}.zip"
        download_asset(asset, archive_path)
        extracted = temporary_root / f"kext-{index}"
        extracted.mkdir()
        safe_extract(archive_path, extracted)

        staged = []
        needs_update = False
        for bundle_name in bundle_names:
            bundle_path = OC_ROOT / "Kexts" / bundle_name
            config_entry = entries.get(bundle_name)
            if config_entry is None:
                raise UpdateError(f"{bundle_name} is not enabled in config.plist")
            source = find_bundle(extracted, bundle_name)
            validate_bundle(source, config_entry)
            incoming_version = bundle_version(source)
            current_version = bundle_version(bundle_path)
            if is_newer(incoming_version, current_version):
                needs_update = True
            else:
                print(
                    f"Keeping {bundle_name} {current_version}; "
                    f"upstream package has {incoming_version}"
                )
            staged.append(
                (bundle_path, source, bundle_name, incoming_version, current_version)
            )

        if needs_update:
            for _, _, bundle_name, incoming_version, current_version in staged:
                if is_newer(current_version, incoming_version):
                    raise UpdateError(
                        f"Refusing {repository} package because updating "
                        f"{bundle_name} would downgrade {current_version} "
                        f"to {incoming_version}"
                    )
            for bundle_path, source, bundle_name, _, _ in staged:
                candidates[bundle_path] = source
                updated.append(f"{repository}: {bundle_name}")
        else:
            print(f"No newer kext release: {repository}")
    return updated


def verify_sha256sums(release: dict, asset: dict, archive_path: Path) -> None:
    checksum_assets = [
        item for item in release["assets"] if item["name"] == "SHA256SUMS.txt"
    ]
    if len(checksum_assets) != 1:
        raise UpdateError("Wireless release is missing its SHA256SUMS.txt asset")
    checksum_text = request_bytes(checksum_assets[0]["browser_download_url"]).decode()
    expected = None
    for line in checksum_text.splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) == 2 and fields[1].lstrip("*").split("/")[-1] == asset["name"]:
            expected = fields[0].lower()
            break
    if expected is None:
        raise UpdateError(f"No SHA-256 entry for {asset['name']}")
    actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if actual != expected:
        raise UpdateError(f"SHA-256 mismatch for {asset['name']}")


def stage_wireless_pair(
    temporary_root: Path,
    config: dict,
    versions: dict,
    candidates: dict[Path, Path],
) -> list[str]:
    repository = "retropineaple/ForbiddenItlwm"
    release = get_latest_release(repository)
    release_tag = release["tag_name"].removeprefix("v")
    current_tag = versions["ForbiddenItlwm"].removeprefix("v")
    if not is_newer(release_tag, current_tag):
        print(f"Keeping ForbiddenItlwm release {current_tag}")
        return []

    entries = bundle_config_entries(config)
    updated = []
    for bundle_name, prefix in (
        ("ForbiddenItlwm.kext", "ForbiddenItlwm-"),
        ("BTLEAdvFixup.kext", "BTLEAdvFixup-"),
    ):
        asset = get_asset(release, prefix, "-Sequoia.zip")
        archive_path = temporary_root / f"{bundle_name}.zip"
        download_asset(asset, archive_path)
        verify_sha256sums(release, asset, archive_path)
        extracted = temporary_root / bundle_name
        extracted.mkdir()
        safe_extract(archive_path, extracted)
        source = find_bundle(extracted, bundle_name)
        config_entry = entries.get(bundle_name)
        if config_entry is None:
            raise UpdateError(f"{bundle_name} is not enabled in config.plist")
        validate_bundle(source, config_entry)
        candidates[OC_ROOT / "Kexts" / bundle_name] = source
        updated.append(f"{repository}: {bundle_name}")

    versions["ForbiddenItlwm"] = release_tag
    return updated


def stage_opencore_update(
    temporary_root: Path,
    config: dict,
    versions: dict,
    candidates: dict[Path, Path],
) -> list[str]:
    repository = "acidanthera/OpenCorePkg"
    release = get_latest_release(repository)
    release_tag = release["tag_name"].removeprefix("v")
    if not is_newer(release_tag, versions["OpenCore"].removeprefix("v")):
        print(f"Keeping OpenCore {versions['OpenCore']}")
        return []

    asset = get_asset(release, f"OpenCore-{release['tag_name']}-", "-RELEASE.zip")
    archive_path = temporary_root / "OpenCore.zip"
    download_asset(asset, archive_path)
    extracted = temporary_root / "OpenCore"
    extracted.mkdir()
    safe_extract(archive_path, extracted)

    source_oc = extracted / "X64" / "EFI" / "OC"
    if not (
        (source_oc / "OpenCore.efi").is_file()
        and (source_oc / "Drivers").is_dir()
        and (source_oc / "Resources").is_dir()
    ):
        raise UpdateError("OpenCore release is missing its X64 EFI/OC files")
    source_efi = source_oc.parent
    source_boot = source_efi / "BOOT" / "BOOTx64.efi"
    if not source_boot.is_file():
        raise UpdateError("OpenCore release is missing X64/EFI/BOOT/BOOTx64.efi")

    for entry in config["UEFI"]["Drivers"]:
        if entry.get("Enabled") is True:
            release_driver = source_oc / "Drivers" / entry["Path"]
            existing_driver = OC_ROOT / "Drivers" / entry["Path"]
            if not release_driver.is_file() and not existing_driver.is_file():
                raise UpdateError(f"OpenCore release is missing driver {entry['Path']}")

    validators = [
        path
        for path in extracted.rglob("ocvalidate")
        if path.is_file() and "Utilities" in path.parts
    ]
    if len(validators) != 1:
        raise UpdateError("OpenCore release is missing a unique ocvalidate binary")
    validator = validators[0]
    validator.chmod(validator.stat().st_mode | stat.S_IXUSR)
    result = subprocess.run(
        [str(validator), str(CONFIG_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise UpdateError(
            "ocvalidate rejected config.plist:\n"
            f"{result.stdout}{result.stderr}"
        )
    print(result.stdout.strip() or "ocvalidate passed")

    staged_oc = temporary_root / "OpenCore-stage"
    staged_oc.mkdir()
    shutil.copy2(source_oc / "OpenCore.efi", staged_oc / "OpenCore.efi")
    staged_drivers = staged_oc / "Drivers"
    shutil.copytree(source_oc / "Drivers", staged_drivers)
    for entry in config["UEFI"]["Drivers"]:
        driver_path = entry["Path"]
        staged_driver = staged_drivers / driver_path
        if staged_driver.is_file():
            continue
        current_driver = OC_ROOT / "Drivers" / driver_path
        if not current_driver.is_file():
            raise UpdateError(
                f"OpenCore release does not provide {driver_path}, "
                "and no existing copy can be preserved"
            )
        staged_driver.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current_driver, staged_driver)
        print(f"Preserving {driver_path}; it is not included in OpenCore releases")
    shutil.copytree(source_oc / "Resources", staged_oc / "Resources")
    staged_boot = temporary_root / "BOOTx64.efi"
    shutil.copy2(source_boot, staged_boot)
    candidates[OC_ROOT / "OpenCore.efi"] = staged_oc / "OpenCore.efi"
    candidates[OC_ROOT / "Drivers"] = staged_oc / "Drivers"
    candidates[OC_ROOT / "Resources"] = staged_oc / "Resources"
    candidates[EFI_ROOT / "BOOT" / "BOOTx64.efi"] = staged_boot
    versions["OpenCore"] = release_tag
    return [
        f"{repository}: OpenCore.efi, BOOTx64.efi, Drivers, Resources ({release_tag})"
    ]


def validate_config_references(config: dict, candidates: dict[Path, Path]) -> None:
    for bundle_path, entry in bundle_config_entries(config).items():
        target = OC_ROOT / "Kexts" / PurePosixPath(bundle_path)
        source = candidates.get(target, target)
        validate_bundle(source, entry)
    for entry in config["UEFI"]["Drivers"]:
        if entry.get("Enabled") is not True:
            continue
        target = OC_ROOT / "Drivers" / entry["Path"]
        driver_root = candidates.get(OC_ROOT / "Drivers", OC_ROOT / "Drivers")
        if target.parent == OC_ROOT / "Drivers":
            source = driver_root / target.name
        else:
            source = candidates.get(target, target)
        if not source.is_file():
            raise UpdateError(f"Configured UEFI driver is missing: {entry['Path']}")


def apply_candidates(candidates: dict[Path, Path]) -> None:
    for target, source in candidates.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        replacement = target.with_name(f".{target.name}.update-tmp")
        if replacement.exists():
            if replacement.is_dir():
                shutil.rmtree(replacement)
            else:
                replacement.unlink()
        if source.is_dir():
            shutil.copytree(source, replacement)
        else:
            shutil.copy2(source, replacement)
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        replacement.replace(target)


def main() -> int:
    import plistlib

    try:
        with CONFIG_PATH.open("rb") as file:
            config = plistlib.load(file)
        versions = json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="efi-driver-update-") as directory:
            temporary_root = Path(directory)
            candidates: dict[Path, Path] = {}
            updated = stage_opencore_update(
                temporary_root, config, versions, candidates
            )
            updated.extend(
                stage_kext_updates(temporary_root, config, candidates)
            )
            updated.extend(
                stage_wireless_pair(temporary_root, config, versions, candidates)
            )
            validate_config_references(config, candidates)
            apply_candidates(candidates)

        if updated:
            VERSIONS_PATH.write_text(
                json.dumps(versions, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("Updated components:")
            for component in updated:
                print(f"- {component}")
        else:
            print("All managed EFI drivers and kexts are up to date.")
        return 0
    except (KeyError, OSError, UpdateError, ValueError, zipfile.BadZipFile) as error:
        print(f"EFI driver update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
