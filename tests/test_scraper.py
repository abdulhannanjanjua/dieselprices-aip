import unittest

from scraper import extract_chart_series


class ExtractChartSeriesTests(unittest.TestCase):
    def test_extracts_named_series_and_rounds_values(self):
        html = """
        <script>
        const chartSeries = [{"name":"Sydney","data":[[1756598400000,180.2143],[1757203200000,181.05]]}];
        const chartTitle = "Sydney";
        </script>
        """

        result = extract_chart_series(html, "Sydney")

        self.assertEqual(result["Sydney"].tolist(), [180.2, 181.0])
        self.assertEqual(result["week_ending"].dt.strftime("%Y-%m-%d").tolist(), ["2025-08-31", "2025-09-07"])

    def test_rejects_missing_chart_data(self):
        with self.assertRaisesRegex(ValueError, "chartSeries"):
            extract_chart_series("<html></html>", "Sydney")


if __name__ == "__main__":
    unittest.main()
