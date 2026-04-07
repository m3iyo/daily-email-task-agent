import csv
import io
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse


def parse_optional_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    for parser in (
        lambda input_text: datetime.fromisoformat(input_text),
        lambda input_text: datetime.strptime(input_text, "%Y-%m-%d"),
    ):
        try:
            return parser(normalized)
        except ValueError:
            continue

    raise HTTPException(status_code=422, detail=f"Invalid datetime value: {value}")


def csv_stream_response(filename_prefix: str, header: list[str], rows: list[list[Any]]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)

    filename = f'{filename_prefix}_{datetime.now().strftime("%Y-%m-%d")}.csv'
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
