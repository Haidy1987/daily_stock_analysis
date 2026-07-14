# -*- coding: utf-8 -*-
"""API-layer tests for technical-chart without importing the full api.v1 package.

Loads Schema by file path so incomplete local envs can still exercise HTTP
status mapping against TechnicalChartService (real indicator engine).
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient

from data_provider.base import DataFetchError, normalize_stock_code
from src.services.technical_chart_service import (
    TechnicalChartService,
    TechnicalChartSourceUnavailableError,
    TechnicalChartValidationError,
)


def _load_schema_module():
    path = Path(__file__).resolve().parents[1] / "api" / "v1" / "schemas" / "technical_chart.py"
    spec = importlib.util.spec_from_file_location("technical_chart_schema_isolated", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.TechnicalChartItem.model_rebuild(_types_namespace=vars(module))
    module.TechnicalChartSummary.model_rebuild(_types_namespace=vars(module))
    module.TechnicalChartResponse.model_rebuild(_types_namespace=vars(module))
    return module


_schema = _load_schema_module()
TechnicalChartResponse = _schema.TechnicalChartResponse

_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"
    r"|(?:SH|SZ|BJ)\d{6}"
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"
    r"|\d{1,5}\.HK"
    r"|HK\d{1,5}"
    r"|\d{5}"
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"
    r")$",
    re.IGNORECASE,
)


def _validate_and_normalize_stock_code(code: str) -> str:
    stripped = code.strip()
    if not stripped or not _STOCK_CODE_RE.match(stripped):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_stock_code", "message": "invalid stock code"},
        )
    return normalize_stock_code(stripped)


def _build_app() -> FastAPI:
    """Mirror production technical-chart endpoint glue for contract tests."""
    app = FastAPI()

    @app.get("/api/v1/stocks/{stock_code}/technical-chart", response_model=TechnicalChartResponse)
    def get_technical_chart(
        stock_code: str,
        period: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
        days: int = Query(120, ge=60, le=250),
        indicators: str | None = Query(None),
    ) -> TechnicalChartResponse:
        canonical = _validate_and_normalize_stock_code(stock_code)
        try:
            result = TechnicalChartService().get_technical_chart(
                stock_code=canonical,
                period=period,
                days=days,
                indicators=indicators,
            )
            return TechnicalChartResponse(**result)
        except TechnicalChartValidationError as exc:
            raise HTTPException(status_code=422, detail={"error": exc.error, "message": exc.message})
        except TechnicalChartSourceUnavailableError as exc:
            raise HTTPException(status_code=503, detail={"error": exc.error, "message": exc.message})

    @app.get("/api/v1/stocks/{stock_code}/history")
    def get_history(stock_code: str):
        from src.services.stock_service import StockService

        result = StockService().get_history_data(stock_code=stock_code, period="daily", days=30)
        return {"stock_code": stock_code, "period": "daily", "data": result.get("data", [])}

    return app


def _ohlcv(n: int = 180) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=n)
    close = pd.Series(np.linspace(50.0, 80.0, n))
    return pd.DataFrame(
        {
            "date": dates,
            "open": close.values,
            "high": close.values + 1,
            "low": close.values - 1,
            "close": close.values,
            "volume": np.full(n, 1000.0),
            "amount": close.values * 1000.0,
            "pct_chg": close.pct_change().fillna(0).values * 100.0,
        }
    )


class TechnicalChartApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(_build_app())

    @patch("data_provider.base.DataFetcherManager")
    def test_default_daily_chart(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (_ohlcv(180), "akshare")
        manager.get_stock_name.return_value = "贵州茅台"

        response = self.client.get("/api/v1/stocks/600519/technical-chart")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["stock_code"], "600519")
        self.assertEqual(body["period"], "daily")
        self.assertEqual(body["range_days"], 120)
        self.assertEqual(len(body["items"]), 120)
        self.assertEqual(body["calculation_version"], "technical-v1")
        self.assertIn(body["data_status"], ["available", "partial"])

    @patch("data_provider.base.DataFetcherManager")
    def test_weekly_supported(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (_ohlcv(800), "akshare")
        manager.get_stock_name.return_value = "贵州茅台"
        response = self.client.get(
            "/api/v1/stocks/600519/technical-chart",
            params={"period": "weekly", "days": 60},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["period"], "weekly")
        self.assertEqual(body["range_days"], 60)
        self.assertEqual(len(body["items"]), 60)
        self.assertEqual(body["calculation_version"], "technical-v1")
        mock_manager_cls.assert_called()

    @patch("data_provider.base.DataFetcherManager")
    def test_monthly_partial_and_illegal_period(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (_ohlcv(90), "akshare")
        manager.get_stock_name.return_value = None
        response = self.client.get(
            "/api/v1/stocks/600519/technical-chart",
            params={"period": "monthly", "days": 60},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["period"], "monthly")
        self.assertEqual(body["data_status"], "partial")
        self.assertLess(len(body["items"]), 60)

        bad = self.client.get(
            "/api/v1/stocks/600519/technical-chart",
            params={"period": "quarterly"},
        )
        self.assertEqual(bad.status_code, 422)

    def test_unknown_indicator_and_days_bounds(self) -> None:
        bad = self.client.get(
            "/api/v1/stocks/600519/technical-chart",
            params={"indicators": "ma,nope"},
        )
        self.assertEqual(bad.status_code, 422)

        days = self.client.get(
            "/api/v1/stocks/600519/technical-chart",
            params={"days": 10},
        )
        self.assertEqual(days.status_code, 422)

    def test_invalid_stock_code(self) -> None:
        response = self.client.get("/api/v1/stocks/!!!/technical-chart")
        self.assertEqual(response.status_code, 400)

    @patch("data_provider.base.DataFetcherManager")
    def test_source_unavailable_503(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.side_effect = DataFetchError("down")
        response = self.client.get("/api/v1/stocks/600519/technical-chart", params={"days": 60})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["error"], "source_unavailable")

    @patch("data_provider.base.DataFetcherManager")
    def test_empty_200(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (pd.DataFrame(), "akshare")
        manager.get_stock_name.return_value = None
        response = self.client.get("/api/v1/stocks/600519/technical-chart", params={"days": 60})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data_status"], "empty")
        self.assertEqual(body["items"], [])

    @patch("data_provider.base.DataFetcherManager")
    def test_history_api_unchanged_empty_on_failure(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.side_effect = DataFetchError("down")
        response = self.client.get("/api/v1/stocks/600519/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])

    def test_legacy_history_still_rejects_weekly(self) -> None:
        """05a decision: aggregation is technical-chart only; StockService stays daily."""
        from src.services.stock_service import StockService

        with self.assertRaises(ValueError) as ctx:
            StockService().get_history_data("600519", period="weekly", days=30)
        self.assertIn("daily", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
