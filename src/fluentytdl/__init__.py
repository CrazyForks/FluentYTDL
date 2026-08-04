"""FluentYTDL package."""

__all__ = ["__version__"]


def _normalize(ver: str) -> str:
    """Strip legacy prefixes so old on-disk VERSION files still parse.

    Releases before 3.5.5 wrote "v-3.0.18" / "pre-3.0.18" / "beta-0.0.5". The
    current format is bare PEP 440 ("3.5.5", "3.5.6-rc.1"); the "v" only ever
    appears on the Git tag. An in-place upgrade can leave an old VERSION file
    next to a new binary, so tolerate both rather than surfacing "v-3.5.5" to
    the update channel logic.
    """
    ver = ver.strip()
    for pfx in ("v-", "pre-", "beta-"):
        if ver.startswith(pfx):
            return ver[len(pfx) :]
    if ver.startswith("v") and ver[1:2].isdigit():
        return ver[1:]
    return ver


def _read_version() -> str:
    """Read version from VERSION file, falling back to importlib.metadata.

    VERSION file stores the bare version like "3.5.5" / "3.5.6-rc.1".
    Priority: VERSION file > importlib.metadata > default.
    """
    import sys
    from pathlib import Path

    # Candidate paths for VERSION file
    candidates = [
        Path(__file__).resolve().parents[2] / "VERSION",  # dev: src/fluentytdl → root
        Path(__file__).resolve().parents[1] / "VERSION",  # alt layout
    ]
    # PyInstaller frozen: VERSION is bundled to _internal/ or exe dir
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.insert(0, exe_dir / "VERSION")
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if str(meipass):
            candidates.insert(0, meipass / "VERSION")

    for p in candidates:
        if p.is_file():
            v = p.read_text(encoding="utf-8").strip()
            if v and v != "0.0.0-dev":
                return _normalize(v)

    # Fallback: pip install -e . reads from pyproject.toml metadata
    try:
        from importlib.metadata import version

        return _normalize(version("FluentYTDL"))
    except Exception:
        pass

    return "0.0.0-dev"


__version__ = _read_version()
