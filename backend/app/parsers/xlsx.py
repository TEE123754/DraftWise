from io import BytesIO

from openpyxl import load_workbook

from app.domain.errors import DomainError
from app.domain.models import SourceBlock


def parse_xlsx(data: bytes, source_id: str, max_cells: int) -> tuple[list[SourceBlock], list[str]]:
    workbook = load_workbook(BytesIO(data), read_only=False, data_only=False, keep_links=False)
    blocks, warnings, traversed = [], [], 0
    try:
        for sheet in workbook:
            # Ignore inflated producer dimensions; still stop traversal at a hard bound.
            if hasattr(sheet, "reset_dimensions"):
                sheet.reset_dimensions()
            sheet_hidden = sheet.sheet_state != "visible"

            # Build sets of hidden rows and columns for per-cell lookup
            hidden_rows: set[int] = set()
            hidden_cols: set[int] = set()
            if hasattr(sheet, "row_dimensions"):
                for row_num, rd in sheet.row_dimensions.items():
                    if rd.hidden:
                        hidden_rows.add(row_num)
            if hasattr(sheet, "column_dimensions"):
                for col_letter, cd in sheet.column_dimensions.items():
                    if cd.hidden:
                        from openpyxl.utils import column_index_from_string
                        hidden_cols.add(column_index_from_string(col_letter))

            for row in sheet.iter_rows():
                traversed += len(row)
                if traversed > max_cells:
                    raise DomainError(
                        "FILE_LIMIT_EXCEEDED",
                        "Worksheet traversal exceeds the cell limit",
                        status=413,
                    )
                for cell in row:
                    if cell.value is None:
                        continue
                    if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
                        warnings.append(
                            f"Formula at {sheet.title}!{cell.coordinate} requires review; cached results are not authoritative"
                        )
                        continue
                    cell_hidden = (
                        sheet_hidden
                        or (cell.row in hidden_rows)
                        or (cell.column in hidden_cols)
                    )
                    blocks.append(
                        SourceBlock(
                            id=f"{source_id}:{sheet.title}:{cell.coordinate}",
                            source_id=source_id,
                            text=str(cell.value),
                            kind="table_cell",
                            locator={
                                "type": "xlsx",
                                "sheet": sheet.title,
                                "cell": cell.coordinate,
                                "row": cell.row,
                                "column": cell.column,
                                "number_format": cell.number_format,
                                "hidden_row": cell.row in hidden_rows,
                                "hidden_col": cell.column in hidden_cols,
                            },
                            hidden=cell_hidden,
                            quality=0.59 if cell_hidden else 1,
                        )
                    )
    finally:
        workbook.close()
    return blocks, warnings[:30]
