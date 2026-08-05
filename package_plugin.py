#!/usr/bin/env python3
"""Build and validate the QGIS plugin ZIP archive."""

import argparse
import configparser
import hashlib
import os
import struct
import xml.etree.ElementTree as ElementTree
import zipfile
from pathlib import Path, PurePosixPath


PLUGIN_SLUG = "attribute_form_toggle"
TRANSLATION_PREFIX = f"{PLUGIN_SLUG}_"
PROJECT_DIRECTORY = Path(__file__).resolve().parent
I18N_DIRECTORY = PROJECT_DIRECTORY / "i18n"
REPOSITORY_DIRECTORY = PROJECT_DIRECTORY / "repo"
ARCHIVE_DIRECTORY = REPOSITORY_DIRECTORY / "plugin"
METADATA_PATH = PROJECT_DIRECTORY / "metadata.txt"
PLUGINS_XML_PATH = REPOSITORY_DIRECTORY / "plugins.xml"

PACKAGE_ROOT_FILES = (
    "__init__.py",
    "main_plugin.py",
    "metadata.txt",
    "icon-cancel.svg",
    "icon.png",
    "README.md",
    "LICENSE",
)
REQUIRED_METADATA_FIELDS = (
    "name",
    "qgisMinimumVersion",
    "description",
    "about",
    "version",
    "author",
    "email",
    "repository",
)
VALID_CATEGORIES = {"Raster", "Vector", "Database", "Web"}


class PackagingError(RuntimeError):
    """Raised when the plugin cannot be packaged safely."""


def read_plugin_metadata():
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(METADATA_PATH, encoding="utf-8"):
        raise PackagingError(f"Cannot read {METADATA_PATH}")

    if "general" not in parser:
        raise PackagingError("metadata.txt does not contain [general]")

    general = parser["general"]
    missing_fields = [
        field for field in REQUIRED_METADATA_FIELDS
        if not general.get(field, "").strip()
    ]
    if missing_fields:
        raise PackagingError(
            "metadata.txt is missing required fields: "
            + ", ".join(missing_fields)
        )

    category = general.get("category", "").strip()
    if category and category not in VALID_CATEGORIES:
        raise PackagingError(
            f"Invalid metadata category {category!r}; expected one of "
            + ", ".join(sorted(VALID_CATEGORIES))
        )

    return general["name"].strip(), general["version"].strip()


def validate_repository_metadata(plugin_name, version, archive_name):
    try:
        plugin = ElementTree.parse(PLUGINS_XML_PATH).getroot().find(
            "pyqgis_plugin"
        )
    except (ElementTree.ParseError, OSError) as error:
        raise PackagingError(
            f"Cannot read {PLUGINS_XML_PATH}: {error}"
        ) from error

    if plugin is None:
        raise PackagingError("plugins.xml does not contain pyqgis_plugin")

    expected_values = {
        "plugin name": (plugin.get("name"), plugin_name),
        "plugin version": (plugin.get("version"), version),
        "version": (plugin.findtext("version"), version),
        "file_name": (plugin.findtext("file_name"), archive_name),
    }
    mismatches = [
        f"{label}: {actual!r} != {expected!r}"
        for label, (actual, expected) in expected_values.items()
        if actual != expected
    ]

    download_url = plugin.findtext("download_url", "")
    if not download_url.endswith(f"/{archive_name}"):
        mismatches.append(
            f"download_url does not end with /{archive_name}"
        )

    if mismatches:
        raise PackagingError(
            "Repository metadata is out of sync:\n- "
            + "\n- ".join(mismatches)
        )


def translation_locale(path, extension):
    return path.name[len(TRANSLATION_PREFIX):-len(extension)]


def collect_package_files():
    root_files = [
        PROJECT_DIRECTORY / file_name
        for file_name in PACKAGE_ROOT_FILES
    ]
    missing_files = [path for path in root_files if not path.is_file()]
    if missing_files:
        missing = ", ".join(str(path) for path in missing_files)
        raise PackagingError(f"Required package files are missing: {missing}")

    ts_files = sorted(I18N_DIRECTORY.glob(f"{TRANSLATION_PREFIX}*.ts"))
    qm_files = sorted(I18N_DIRECTORY.glob(f"{TRANSLATION_PREFIX}*.qm"))
    ts_locales = {translation_locale(path, ".ts") for path in ts_files}
    qm_locales = {translation_locale(path, ".qm") for path in qm_files}

    if not ts_files or ts_locales != qm_locales:
        missing_qm = sorted(ts_locales - qm_locales)
        missing_ts = sorted(qm_locales - ts_locales)
        raise PackagingError(
            "Translation pairs are incomplete: "
            f"missing QM={missing_qm}, missing TS={missing_ts}"
        )

    empty_files = [
        path for path in (*ts_files, *qm_files) if path.stat().st_size == 0
    ]
    if empty_files:
        empty = ", ".join(str(path) for path in empty_files)
        raise PackagingError(f"Empty translation files found: {empty}")

    return root_files + ts_files + qm_files, len(ts_locales)


def archive_name_for(path):
    relative_path = path.relative_to(PROJECT_DIRECTORY)
    return (
        PurePosixPath(PLUGIN_SLUG) / PurePosixPath(relative_path.as_posix())
    ).as_posix()


def local_header_names(archive_path):
    archive_data = archive_path.read_bytes()
    signature = b"PK" + bytes((3, 4))
    position = 0
    names = []

    while archive_data[position:position + 4] == signature:
        compressed_size = struct.unpack_from(
            "<I",
            archive_data,
            position + 18,
        )[0]
        name_length, extra_length = struct.unpack_from(
            "<HH",
            archive_data,
            position + 26,
        )
        name_start = position + 30
        names.append(archive_data[name_start:name_start + name_length])
        position = (
            name_start
            + name_length
            + extra_length
            + compressed_size
        )

    return names


def validate_archive(archive_path, package_files):
    expected_names = {
        archive_name_for(path): path for path in package_files
    }

    with zipfile.ZipFile(archive_path) as archive:
        bad_file = archive.testzip()
        if bad_file:
            raise PackagingError(f"Corrupt ZIP entry: {bad_file}")

        archive_names = archive.namelist()
        if (
            len(archive_names) != len(expected_names)
            or set(archive_names) != set(expected_names)
        ):
            raise PackagingError("ZIP file list does not match package files")
        if any("\\" in name for name in archive_names):
            raise PackagingError("ZIP central directory contains backslashes")

        for archive_name, source_path in expected_names.items():
            if archive.read(archive_name) != source_path.read_bytes():
                raise PackagingError(
                    f"ZIP content differs from source: {archive_name}"
                )

    header_names = local_header_names(archive_path)
    if len(header_names) != len(expected_names):
        raise PackagingError("ZIP local header count is incorrect")
    if any(bytes((92,)) in name for name in header_names):
        raise PackagingError("ZIP local headers contain backslashes")


def sha256_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as archive_file:
        for chunk in iter(lambda: archive_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_archive(keep_old):
    plugin_name, version = read_plugin_metadata()
    archive_name = f"{PLUGIN_SLUG}.{version}.zip"
    validate_repository_metadata(plugin_name, version, archive_name)
    package_files, locale_count = collect_package_files()

    ARCHIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIRECTORY / archive_name
    temporary_path = ARCHIVE_DIRECTORY / f".{archive_name}.tmp"
    temporary_path.unlink(missing_ok=True)

    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=False,
        ) as archive:
            for source_path in package_files:
                archive.write(
                    source_path,
                    arcname=archive_name_for(source_path),
                )

        validate_archive(temporary_path, package_files)
        os.replace(temporary_path, archive_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    removed_archives = []
    if not keep_old:
        for old_archive in ARCHIVE_DIRECTORY.glob(
            f"{PLUGIN_SLUG}.*.zip"
        ):
            if old_archive != archive_path:
                old_archive.unlink()
                removed_archives.append(old_archive.name)

    print(f"Created: {archive_path}")
    print(
        f"Files: {len(package_files)}; locales: {locale_count}; "
        "ZIP paths: POSIX"
    )
    print(f"SHA-256: {sha256_digest(archive_path)}")
    if removed_archives:
        print("Removed old archives: " + ", ".join(removed_archives))


def main():
    argument_parser = argparse.ArgumentParser(
        description="Build and validate the Attribute Form Toggle ZIP."
    )
    argument_parser.add_argument(
        "--keep-old",
        action="store_true",
        help="Do not remove older attribute_form_toggle.*.zip archives.",
    )
    arguments = argument_parser.parse_args()

    try:
        build_archive(arguments.keep_old)
    except (OSError, PackagingError, zipfile.BadZipFile) as error:
        argument_parser.exit(1, f"Packaging failed: {error}\n")


if __name__ == "__main__":
    main()
