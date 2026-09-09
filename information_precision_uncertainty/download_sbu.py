from __future__ import annotations

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

from .sbu import SBU_URL


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official Atlanta Fed SBU microdata.")
    parser.add_argument("--output-dir", default="information_precision_uncertainty/data/raw")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(SBU_URL) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    member = next(name for name in archive.namelist() if name.endswith("SBU_microdata.dta"))
    target = output / "SBU_microdata.dta"
    with archive.open(member) as source, target.open("wb") as destination:
        while chunk := source.read(1024 * 1024):
            destination.write(chunk)
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()

