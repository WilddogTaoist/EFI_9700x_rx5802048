#!/usr/bin/env python3
"""Assemble a local EFI from the published template and verified dependencies."""

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import subprocess
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent
CONFIG = "EFI/OC/config.plist"
BLUETOOTH = "EFI/OC/Kexts/RealtekBluetoothFirmware.kext"
IDENTITY_KEYS = ("MLB", "ROM", "SystemSerialNumber", "SystemUUID")


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"Unexpected archive path: {name}")
    return path


def store_file(root, name, data):
    target = root / safe_path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != data:
        raise ValueError(f"Conflicting dependency file: {name}")
    target.write_bytes(data)


def get_archive(item, cache):
    filename = cache / (item["sha256"] + ".zip")
    if not filename.exists():
        request = Request(item["url"], headers={"User-Agent": "EFI-9700X-builder"})
        with urlopen(request, timeout=45) as remote:
            data = remote.read()
        if sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"Unexpected SHA-256: {item['url']}")
        filename.write_bytes(data)
    if sha256(filename.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError(f"Invalid cached archive: {filename}")
    return filename


def copy_archive(item, root, cache):
    with ZipFile(get_archive(item, cache)) as archive:
        members = [name for name in archive.namelist()
                   if not name.endswith("/") and not any(name.startswith(p) for p in item.get("skip", []))]
        for rule in item["copy"]:
            origin, destination = rule["from"], rule["to"]
            if origin.endswith("/"):
                selected = [name for name in members if name.startswith(origin)]
                if not selected:
                    raise ValueError(f"No files found under {origin}")
                for name in selected:
                    store_file(root, destination + name[len(origin):], archive.read(name))
            else:
                if origin not in members:
                    raise ValueError(f"Missing dependency file: {origin}")
                store_file(root, destination, archive.read(origin))


def restore_assets(root, backup):
    with ZipFile(backup) as archive:
        for name in archive.namelist():
            p = safe_path(name)
            if (p.parts[:1] == ("EFI",) and not name.endswith("/")
                    and not any(part.startswith("._") for part in p.parts)
                    and "config.pre-" not in p.name and name != CONFIG):
                store_file(root, name, archive.read(name))


def personalize(root, identity_file):
    cfg = plistlib.loads((root / CONFIG).read_bytes())
    if identity_file:
        identity = plistlib.loads(identity_file.read_bytes())["PlatformInfo"]["Generic"]
        if identity["SystemProductName"] != cfg["PlatformInfo"]["Generic"]["SystemProductName"]:
            raise ValueError("The local identity must use the same SMBIOS model as the template.")
        if not all(identity[key] for key in IDENTITY_KEYS) or len(identity["ROM"]) != 6:
            raise ValueError("The local identity is incomplete.")
        for key in IDENTITY_KEYS:
            cfg["PlatformInfo"]["Generic"][key] = identity[key]
        (root / CONFIG).write_bytes(plistlib.dumps(cfg, sort_keys=False))
    return cfg


def check_required(root, config):
    paths = ["EFI/BOOT/BOOTx64.efi", "EFI/OC/OpenCore.efi",
             "EFI/OC/Resources/Image/Acidanthera/GoldenGate/Windows.icns"]
    for entry in config["Kernel"]["Add"]:
        if entry["Enabled"]:
            base = PurePosixPath("EFI/OC/Kexts") / entry["BundlePath"]
            paths.append(base / entry["PlistPath"])
            if entry["ExecutablePath"]:
                paths.append(base / entry["ExecutablePath"])
    for entry in config["UEFI"]["Drivers"]:
        if entry["Enabled"]:
            paths.append(PurePosixPath("EFI/OC/Drivers") / entry["Path"])
    for entry in config["ACPI"]["Add"]:
        if entry["Enabled"]:
            paths.append(PurePosixPath("EFI/OC/ACPI") / entry["Path"])
    missing = [str(path) for path in paths if not (root / path).is_file()]
    if missing:
        raise ValueError("Missing EFI dependencies: " + ", ".join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".efi-cache"))
    parser.add_argument("--from-backup", type=Path, help="read dependencies from a private local EFI ZIP")
    parser.add_argument("--bluetooth-kext", type=Path, help="path to a local RealtekBluetoothFirmware.kext")
    parser.add_argument("--identity-plist", type=Path, help="your private, working OpenCore config.plist")
    parser.add_argument("--ocvalidate", type=Path, help="optional path to ocvalidate from OpenCore 1.0.8")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    if not args.from_backup and not args.bluetooth_kext:
        parser.error("provide --bluetooth-kext for an online build, or use --from-backup")
    if args.bluetooth_kext:
        info = plistlib.loads((args.bluetooth_kext / "Contents/Info.plist").read_bytes())
        if info["CFBundleIdentifier"] != "org.thegwchr.RealtekBluetoothFirmware" or info["CFBundleVersion"] != "1.0.2":
            parser.error("expected RealtekBluetoothFirmware 1.0.2")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="efi-build-", dir=args.output.parent) as directory:
        root = Path(directory) / "result"
        shutil.copytree(ROOT / "EFI", root / "EFI")
        if args.from_backup:
            restore_assets(root, args.from_backup)
        else:
            args.cache_dir.mkdir(parents=True, exist_ok=True)
            for item in json.loads((ROOT / "dependencies.json").read_text()):
                copy_archive(item, root, args.cache_dir)
            shutil.copytree(args.bluetooth_kext, root / BLUETOOTH)
        check_required(root, personalize(root, args.identity_plist))
        if args.ocvalidate:
            subprocess.run([str(args.ocvalidate.resolve()), str(root / CONFIG)], check=True)
        root.rename(args.output)
    print(f"EFI assembled in {args.output / 'EFI'}")
    if not args.identity_plist:
        print("Fill your private PlatformInfo/Generic before booting.")


if __name__ == "__main__":
    main()
