from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management import execute_from_command_line
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import path
from django import setup


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DATABASE_PATH = REPO_ROOT / "database" / "prediction_market.db"
EXPORTS_PATH = REPO_ROOT / "database" / "exports"


if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="development-only-secret-key",
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["127.0.0.1", "localhost"],
        INSTALLED_APPS=[],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [REPO_ROOT / "frontend"],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [],
                },
            }
        ],
    )


setup()


def index(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    return render(request, "index.html")


def datatable(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    return render(request, "datatable.html")


DATA_COLUMNS = [
    "calendar_date",
    "market_hour_id",
    "hour_start",
    "hour_end",
    "observation_id",
    "observed_at",
    "asset_id",
    "token_id",
    "outcome",
    "price_symbol",
    "price",
    "price_source",
    "order_book_state_id",
    "best_bid",
    "best_ask",
]


def _parse_timestamp(value: str | None, parameter_name: str) -> str | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{parameter_name} mora biti valjan ISO-8601 datum.") from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    milliseconds = parsed.microsecond // 1000
    return parsed.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds:03d}Z"


def _query_parameters(request: HttpRequest) -> tuple[list[object], str]:
    clauses: list[str] = []
    parameters: list[object] = []

    start = _parse_timestamp(request.GET.get("start"), "start")
    end = _parse_timestamp(request.GET.get("end"), "end")
    if start:
        clauses.append("o.observed_at >= ?")
        parameters.append(start)
    if end:
        clauses.append("o.observed_at <= ?")
        parameters.append(end)

    outcome = request.GET.get("outcome")
    if outcome in {"Up", "Down"}:
        clauses.append("ma.outcome = ?")
        parameters.append(outcome)

    market_hour_id = request.GET.get("market_hour_id")
    if market_hour_id:
        try:
            parameters.append(int(market_hour_id))
        except ValueError as error:
            raise ValueError("market_hour_id mora biti cijeli broj.") from error
        clauses.append("mh.market_hour_id = ?")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return parameters, where


def _fetch_records(request: HttpRequest) -> list[dict[str, object]]:
    parameters, where = _query_parameters(request)
    query = f"""
        SELECT td.calendar_date, mh.market_hour_id, mh.hour_start, mh.hour_end,
               o.observation_id, o.observed_at, ma.asset_id, ma.token_id,
               ma.outcome, cp.symbol AS price_symbol, cp.price,
               cp.source AS price_source, obs.order_book_state_id,
               obs.best_bid, obs.best_ask
        FROM observation AS o
        JOIN market_hour AS mh ON mh.market_hour_id = o.market_hour_id
        JOIN trading_date AS td ON td.trading_date_id = mh.trading_date_id
        JOIN order_book_state AS obs ON obs.observation_id = o.observation_id
        JOIN market_asset AS ma ON ma.asset_id = obs.asset_id
        LEFT JOIN crypto_price AS cp ON cp.observation_id = o.observation_id
        {where}
        ORDER BY o.observed_at, ma.outcome
    """
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, parameters)]


def _data_response(request: HttpRequest, output_format: str) -> HttpResponse:
    if request.method != "GET":
        return HttpResponse(status=405)

    try:
        records = _fetch_records(request)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    if output_format == "json":
        return JsonResponse(records, safe=False, json_dumps_params={"indent": 2})

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=DATA_COLUMNS)
    writer.writeheader()
    writer.writerows(records)
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="filtered-data.csv"'
    return response


def data_api(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"error": "Dopušten je samo GET zahtjev."}, status=405)
    try:
        records = _fetch_records(request)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(
        {"count": len(records), "records": records},
        json_dumps_params={"indent": 2},
    )


def raw_export(request: HttpRequest, filename: str) -> FileResponse | HttpResponse:
    files = {
        "all.csv": "text/csv",
        "all.json": "application/json",
        "schema.json": "application/schema+json",
    }
    if request.method != "GET" or filename not in files:
        return HttpResponse(status=404)
    export_path = REPO_ROOT / filename if filename == "schema.json" else EXPORTS_PATH / filename
    if not export_path.is_file():
        return HttpResponse("Export datoteka nije pronađena.", status=404)
    return FileResponse(export_path.open("rb"), content_type=files[filename])


urlpatterns = [
    path("", index, name="index"),
    path("datatable/", datatable, name="datatable"),
    path("api/data/", data_api, name="data-api"),
    path("api/data.json", lambda request: _data_response(request, "json"), name="data-json"),
    path("api/data.csv", lambda request: _data_response(request, "csv"), name="data-csv"),
    path("data/<str:filename>", raw_export, name="raw-export"),
    path("schema.json", lambda request: raw_export(request, "schema.json"), name="schema"),
]


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server")
    execute_from_command_line(["server.py", "runserver", "127.0.0.1:8000"])