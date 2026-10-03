import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "generate_catalog.py"
spec = importlib.util.spec_from_file_location("generator", MODULE)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class GeneratorRulesTest(unittest.TestCase):
    def test_wisp_pair(self):
        p = g.enrich_product({
            "id": "x",
            "name": "Wisp black bar end mirrors a pair for M8 threaded handlebars",
            "url": "https://example.com/x-detail",
            "usd": 186,
            "ntd": 4464,
            "soldOut": False,
            "images": [],
        })
        self.assertEqual(p["shortName"], "WISP")
        self.assertEqual(p["chips"], ["M8", "標準車把端", "黑色", "一對"])
        self.assertEqual(p["summary"], "黑色・標準車把端・M8 車把端安裝・左右一對")
        self.assertNotIn("來源售價", [x[0] for x in p["specs"]])

    def test_rh_short_name(self):
        p = g.enrich_product({
            "id": "x",
            "name": "Wisp black bar end mirror RH a piece for M8 threaded handlebars",
            "url": "https://example.com/x-detail",
            "usd": 101,
            "ntd": 2424,
            "soldOut": False,
            "images": [],
        })
        self.assertEqual(p["shortName"], "WISP RH")
        self.assertEqual(p["package"], "右側單支")

    def test_confirmed_mixed_adapter_excluded(self):
        card = """
        <a href="https://kiwavmotors.com/en/x-detail">Quick View</a>
        <div>Quick View Blok black motorcycle mirrors fairing mount with chrome adapter $164 USD</div>
        <img src="https://cdn.kiwavmotors.com/products/images/main/resized/100__1_280x280.jpg">
        """
        self.assertIsNone(g.extract_product(card, 30, 0.8))

    def test_config_defaults(self):
        ps = [{"id": "a"}, {"id": "b"}]
        cfg = g.build_config(ps, None)
        self.assertEqual(cfg["products"], {"a": True, "b": True})
        self.assertTrue(cfg["showSoldOut"])
        self.assertTrue(cfg["enableZoom"])
        self.assertFalse(cfg["showWeight"])
        self.assertEqual(cfg["detailImageLimit"], 0)


if __name__ == "__main__":
    unittest.main()
