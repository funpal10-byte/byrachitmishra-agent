import unittest
from agent.schema import validate_visual
from agent.config import load_brand, BRAND_FILE, ROOT


class EditorialContractTests(unittest.TestCase):
    def test_active_brief_contains_current_territory_and_valid_slots(self):
        brand = load_brand()
        self.assertEqual(BRAND_FILE, ROOT / "brand.yml")
        self.assertIn("heavy industry", brand.identity["positioning"])
        self.assertEqual(brand.design["accent"], "#b0492a")
        self.assertTrue(all(s["pillar"] in brand.pillars for s in brand.slots))
        self.assertEqual(len(brand.slots), 10)
        self.assertEqual(sum(s.get("source") == "blog" for s in brand.slots), 3)
        self.assertEqual(len({(s['day'], s['time']) for s in brand.slots}), 10)

    def test_comparison_rejects_extra_items_and_missing_basis(self):
        obj = {"kind": "comparison", "items": [{"label": "A", "detail": "B"}]*3}
        problems = validate_visual(obj, "example")
        self.assertTrue(any("exactly two" in p for p in problems))
        self.assertTrue(any("basis note" in p for p in problems))

    def test_bad_visual_data_is_a_quality_error(self):
        self.assertTrue(validate_visual({"kind": "checklist", "items": [None, {}]}, "example"))
