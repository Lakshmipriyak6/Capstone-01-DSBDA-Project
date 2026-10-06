import csv
import io
import json
from typing import List, Dict, Iterator, Optional


class CSVIndexer:
    """Create and use a lightweight byte-offset index for large CSVs.

    Index stores offsets for every `index_interval` data rows (not counting header).
    This keeps the index small while allowing O(index_interval) seeks to reach any row.
    """

    def __init__(self, csv_path: str, index_path: Optional[str] = None, index_interval: int = 1000):
        self.csv_path = csv_path
        self.index_path = index_path or csv_path + '.idx.json'
        self.index_interval = index_interval
        self.header_fields: List[str] = []
        self.offsets: List[int] = []
        self.first_data_offset: int = 0
        self.total_rows: int = 0

    def build_index(self, force: bool = False) -> Dict:
        """Scan the CSV once and write a compact index file.

        Returns the index metadata dict.
        """
        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                if not force:
                    data = json.load(f)
                    self._load_from_dict(data)
                    return data
        except FileNotFoundError:
            pass

        offsets = []
        total = 0
        with open(self.csv_path, 'rb') as bf:
            # read header line
            header_bytes = bf.readline()
            self.first_data_offset = bf.tell()
            header_line = header_bytes.decode('utf-8', errors='replace').rstrip('\n')
            # parse header robustly
            reader = csv.reader([header_line])
            self.header_fields = next(reader)

            while True:
                pos = bf.tell()
                line = bf.readline()
                if not line:
                    break
                total += 1
                if total % self.index_interval == 0:
                    offsets.append(pos)

        self.offsets = offsets
        self.total_rows = total
        meta = {
            'csv_path': self.csv_path,
            'index_interval': self.index_interval,
            'first_data_offset': self.first_data_offset,
            'offsets': self.offsets,
            'total_rows': self.total_rows,
            'header_fields': self.header_fields,
        }
        with open(self.index_path, 'w', encoding='utf-8') as out:
            json.dump(meta, out)
        return meta

    def _load_from_dict(self, data: Dict):
        self.header_fields = data.get('header_fields', [])
        self.offsets = data.get('offsets', [])
        self.first_data_offset = data.get('first_data_offset', 0)
        self.total_rows = data.get('total_rows', 0)
        self.index_interval = data.get('index_interval', self.index_interval)

    def load_index(self):
        with open(self.index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._load_from_dict(data)
        return data

    def iter_chunks(self, chunk_size: int = 1000) -> Iterator[List[Dict[str, str]]]:
        """Stream the CSV and yield lists of rows as dicts of length up to chunk_size."""
        with open(self.csv_path, 'r', encoding='utf-8', newline='') as tf:
            reader = csv.DictReader(tf)
            chunk = []
            for row in reader:
                chunk.append(row)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk

    def get_row_by_number(self, n: int) -> Optional[Dict[str, str]]:
        """Return the n-th data row (0-based) as a dict, or None if out of range.

        Uses the compact index to seek near the desired row and then parse forward.
        """
        if n < 0:
            return None
        # ensure index loaded
        if not self.header_fields:
            self.load_index()

        if n >= self.total_rows:
            return None

        # find nearest checkpoint
        checkpoint = (n // self.index_interval) * self.index_interval
        if checkpoint == 0:
            seek_pos = self.first_data_offset
        else:
            idx = checkpoint // self.index_interval - 1
            # offsets store positions for rows at index_interval, 2*index_interval, ...
            # so offset for checkpoint is offsets[idx]
            seek_pos = self.offsets[idx]

        with open(self.csv_path, 'rb') as bf:
            bf.seek(seek_pos)
            tf = io.TextIOWrapper(bf, encoding='utf-8', newline='')
            # use DictReader but supply fieldnames so parsing works mid-file
            reader = csv.DictReader(tf, fieldnames=self.header_fields)
            # if we started at first_data_offset, the first read is the row for checkpoint
            start = checkpoint
            for i, row in enumerate(reader):
                cur = start + i
                if cur == n:
                    return row
        return None

    def search(self, column: str, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Simple streaming search: returns up to max_results rows where `query` is substring of `column`."""
        results = []
        for chunk in self.iter_chunks(1000):
            for row in chunk:
                val = row.get(column, '')
                if val and query in val:
                    results.append(row)
                    if len(results) >= max_results:
                        return results
        return results
