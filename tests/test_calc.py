"""Тесты калькулятора юнит-экономики skills/unit-economics/calc.py."""
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

CALC_PATH = Path(__file__).resolve().parent.parent / "skills" / "unit-economics" / "calc.py"
spec = importlib.util.spec_from_file_location("calc", CALC_PATH)
calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc)


def parse(*argv):
    return calc.build_parser().parse_args(list(argv))


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = calc.main(list(argv))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


BASE = ["--price", "1990", "--cost", "650", "--commission", "24.5",
        "--logistics", "90", "--return-logistics", "50", "--buyout", "85",
        "--storage", "12", "--ads-pct", "8", "--tax", "usn6"]


class UnitEconomicsTest(unittest.TestCase):
    def test_matches_manual_calculation(self):
        args = parse(*BASE)
        result = calc.unit_economics(args, 1990)
        logistics = (90 + 0.15 * 50) / 0.85
        expected = 1990 - 650 - 1990 * 0.245 - logistics - 12 - 1990 * 0.08 - 1990 * 0.06
        self.assertAlmostEqual(result["Прибыль"], expected, places=6)
        self.assertAlmostEqual(result["Логистика на выкуп (с учётом невыкупов)"], logistics)
        self.assertAlmostEqual(result["Налог"], 1990 * 0.06)

    def test_full_buyout_has_no_return_logistics(self):
        args = parse("--price", "1000", "--cost", "300", "--commission", "20",
                     "--logistics", "100", "--return-logistics", "70")
        result = calc.unit_economics(args, 1000)
        self.assertAlmostEqual(result["Логистика на выкуп (с учётом невыкупов)"], 100)

    def test_lower_buyout_lowers_profit(self):
        high = calc.unit_economics(parse(*BASE), 1990)["Прибыль"]
        low = calc.unit_economics(parse(*BASE, "--buyout", "50"), 1990)["Прибыль"]
        self.assertLess(low, high)

    def test_usn6_taxes_full_price_not_payout(self):
        args = parse("--price", "1000", "--cost", "300", "--commission", "50")
        self.assertAlmostEqual(calc.unit_economics(args, 1000)["Налог"], 60)

    def test_usn15_taxes_income_minus_expenses(self):
        args = parse("--price", "1000", "--cost", "300", "--commission", "20", "--tax", "usn15")
        result = calc.unit_economics(args, 1000)
        self.assertAlmostEqual(result["Налог"], (1000 - 300 - 200) * 0.15)
        self.assertAlmostEqual(result["Прибыль"], 500 - 75)

    def test_usn15_no_negative_tax_on_loss(self):
        args = parse("--price", "100", "--cost", "300", "--commission", "20", "--tax", "usn15")
        self.assertEqual(calc.unit_economics(args, 100)["Налог"], 0)

    def test_vat_is_extracted_from_price(self):
        args = parse("--price", "1050", "--cost", "0", "--commission", "0",
                     "--tax", "none", "--vat", "5")
        result = calc.unit_economics(args, 1050)
        self.assertAlmostEqual(result["НДС"], 50)
        self.assertAlmostEqual(result["Прибыль"], 1000)

    def test_ads_rub_and_pct_add_up(self):
        args = parse("--price", "1000", "--cost", "0", "--commission", "0",
                     "--ads", "30", "--ads-pct", "5", "--tax", "none")
        self.assertAlmostEqual(calc.unit_economics(args, 1000)["Реклама"], 80)


class SolvePriceTest(unittest.TestCase):
    def test_breakeven_gives_zero_profit(self):
        args = parse(*BASE)
        price = calc.solve_price(args, 0)
        self.assertAlmostEqual(calc.unit_economics(args, price)["Прибыль"], 0, places=2)

    def test_target_margin_is_reached(self):
        args = parse(*BASE)
        price = calc.solve_price(args, 20)
        self.assertAlmostEqual(calc.margin(calc.unit_economics(args, price)), 20, places=3)

    def test_impossible_margin_returns_none(self):
        args = parse("--price", "100", "--cost", "50", "--commission", "60", "--ads-pct", "40")
        self.assertIsNone(calc.solve_price(args, 0))


class CliTest(unittest.TestCase):
    def test_prints_report(self):
        code, out, _ = run_cli(*BASE, "--target-margin", "20")
        self.assertEqual(code, 0)
        self.assertIn("Прибыль", out)
        self.assertIn("447 ₽", out)
        self.assertIn("Точка безубыточности: 1 263 ₽", out)
        self.assertIn("Цена для маржи 20%: 1 872 ₽", out)

    def test_reports_unreachable_breakeven(self):
        code, out, _ = run_cli("--price", "100", "--cost", "50",
                               "--commission", "60", "--ads-pct", "40")
        self.assertEqual(code, 0)
        self.assertIn("не найдена", out)

    def test_rejects_zero_buyout(self):
        code, _, err = run_cli("--price", "100", "--cost", "50",
                               "--commission", "10", "--buyout", "0")
        self.assertEqual(code, 2)
        self.assertIn("--buyout", err)

    def test_rejects_non_positive_price(self):
        code, _, err = run_cli("--price", "0", "--cost", "50", "--commission", "10")
        self.assertEqual(code, 2)
        self.assertIn("--price", err)

    def test_requires_mandatory_arguments(self):
        code, _, _ = run_cli("--price", "100")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
