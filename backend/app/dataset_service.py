"""Lightweight, streaming access to the bundled SQuAD dataset."""

import csv
from pathlib import Path
from typing import Any


DATASET_PATH = Path(__file__).resolve().parents[2] / "dataset" / "DocuMind_AI_SQuAD2_Dataset.csv"


class DatasetService:
    """Expose dataset metadata without materializing the CSV's rows in memory."""

    def __init__(self, csv_path: Path = DATASET_PATH):
        self.csv_path = csv_path
        self._cached_stats: dict[str, Any] | None = None
        self._cached_signature: tuple[int, int] | None = None

    def get_stats(self) -> dict[str, Any]:
        try:
            signature = (self.csv_path.stat().st_mtime_ns, self.csv_path.stat().st_size)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Dataset file was not found: {self.csv_path}") from exc

        if self._cached_stats is not None and signature == self._cached_signature:
            return self._cached_stats.copy()

        # csv.reader streams one record at a time, so large contexts never accumulate
        # in process memory. It also counts correctly if a quoted field spans lines.
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as dataset_file:
            reader = csv.reader(dataset_file)
            columns = next(reader, [])
            row_count = sum(1 for _ in reader)

        stats = {"row_count": row_count, "columns": columns}
        self._cached_signature = signature
        self._cached_stats = stats
        return stats.copy()


dataset_service = DatasetService()
