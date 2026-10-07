"""Цифры в примерах docs/examples должны совпадать с расчётами калькулятора и данными."""
import csv
import importlib.util
import re
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "docs" / "examples"

spec = importlib.util.spec_from_file_location("calc", ROOT / "skills" / "unit-economics" / "calc.py")
calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc)

# Бежевая скатерть «Лён и Дом» — параметры из примера 4.
SKATERT = ["--price", "2490", "--cost", "820", "--commission", "22", "--logistics", "95",
           "--return-logistics", "50", "--buyout", "92", "--storage", "9",
           "--ads-pct", "7", "--tax", "usn6"]


def read(name):
    return (EXAMPLES / name).read_text(encoding="utf-8")


def rub(value):
    """Формат, как в примерах: 1 441 (неразрывный пробел не используется)."""
    return f"{round(value):,}".replace(",", " ")


def profit(price, *extra):
    args = calc.build_parser().parse_args(SKATERT + list(extra))
    result = calc.unit_economics(args, price)
    return result["Прибыль"], calc.margin(result)


def pct(value):
    return f"{value:.1f}".replace(".", ",") + "%"


class LinksTest(unittest.TestCase):
    def test_local_links_exist(self):
        for page in EXAMPLES.glob("*.md"):
            text = page.read_text(encoding="utf-8")
            for link in re.findall(r"\]\(((?!https?://|#)[^)]+)\)", text):
                with self.subTest(page=page.name, link=link):
                    self.assertTrue((page.parent / link).resolve().exists(), link)

    def test_index_lists_every_example(self):
        index = read("README.md")
        for page in sorted(EXAMPLES.glob("0*.md")):
            with self.subTest(page=page.name):
                self.assertIn(f"]({page.name})", index)


class UnitEconomicsExampleTest(unittest.TestCase):
    def test_headline_numbers(self):
        text = read("04-unit-economics.md")
        args = calc.build_parser().parse_args(SKATERT)
        value, margin = profit(2490)
        self.assertIn(f"Прибыль с единицы: {rub(value)} ₽ · маржа {pct(margin)}", text)
        self.assertIn(f"Точка безубыточности: {rub(calc.solve_price(args, 0))} ₽", text)
        self.assertIn(f"цена для маржи 20%: {rub(calc.solve_price(args, 20))} ₽", text)

    def test_sensitivity_rows(self):
        text = read("04-unit-economics.md")
        cases = [
            ("Цена −10% (2 241 ₽)", profit(2241)),
            ("Выкуп упал до 77%", profit(2490, "--buyout", "77")),
            ("Реклама выросла до ДРР 12%", profit(2490, "--ads-pct", "12")),
            ("Скидка 15% в акции (2 116 ₽)", profit(2116)),
        ]
        for label, (value, margin) in cases:
            with self.subTest(label=label):
                self.assertIn(f"| {label} | {rub(value)} ₽ | {pct(margin)} |", text)


class PriceMonitorExampleTest(unittest.TestCase):
    def test_promo_table(self):
        text = read("06-price-monitor.md")
        for discount in (10, 15, 20, 25, 30):
            price = round(2490 * (1 - discount / 100))
            value, margin = profit(price)
            row = re.search(rf"\| \**{discount}%\** \| \**{rub(price)} ₽\** \| \**{rub(value)} ₽\** \| \**{re.escape(pct(margin))}\** \|", text)
            with self.subTest(discount=discount):
                self.assertIsNotNone(row)

    def test_minimum_price(self):
        text = read("06-price-monitor.md")
        args = calc.build_parser().parse_args(SKATERT)
        self.assertIn(f"Минимальная цена с маржой 10%: **{rub(calc.solve_price(args, 10))} ₽**", text)
        self.assertIn(f"Ниже {rub(calc.solve_price(args, 0))} ₽ — убыток", text)

    def test_competitor_a_price_scenario(self):
        value, margin = profit(2190)
        self.assertIn(f"с 682 до {rub(value)} ₽ с единицы (маржа {pct(margin)})", read("06-price-monitor.md"))


class SalesReportExampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = EXAMPLES / "data"
        cost = {r["Артикул продавца"]: float(r["Себестоимость, ₽"])
                for r in csv.DictReader((data / "cost.csv").open(encoding="utf-8"))}
        items = defaultdict(lambda: defaultdict(float))
        for r in csv.DictReader((data / "wb-report-week.csv").open(encoding="utf-8")):
            item = items[r["Артикул продавца"]]
            kind = r["Обоснование для оплаты"]
            sign = -1 if kind == "Возврат" else 1
            if kind in ("Продажа", "Возврат"):
                item["qty"] += sign * float(r["Кол-во"])
                item["rev"] += sign * float(r["Реализовано, ₽"])
                item["pay"] += sign * float(r["К перечислению продавцу, ₽"])
            item["out"] += (float(r["Доставка покупателю, ₽"]) + float(r["Хранение, ₽"])
                            + float(r["Штрафы, ₽"]))
        cls.items = {}
        for name, item in items.items():
            transfer = item["pay"] - item["out"]
            cls.items[name] = {
                "qty": item["qty"], "rev": item["rev"], "transfer": transfer,
                "profit": transfer - cost[name] * item["qty"] - item["rev"] * 0.06,
            }
        cls.text = read("05-sales-report.md")

    def test_totals(self):
        rev = sum(i["rev"] for i in self.items.values())
        transfer = sum(i["transfer"] for i in self.items.values())
        total = sum(i["profit"] for i in self.items.values())
        self.assertIn(f"Продажи: {rub(rev)} ₽ · К перечислению: {rub(transfer)} ₽", self.text)
        self.assertIn(f"{transfer:,.2f}".replace(",", " ").replace(".", ","), self.text)
        self.assertIn(f"Прибыль: {rub(total)} ₽", self.text)

    def test_per_item_profit(self):
        for name, item in self.items.items():
            with self.subTest(item=name):
                row = next(line for line in self.text.splitlines() if line.startswith(f"| {name} |"))
                self.assertIn(f"| {rub(item['qty'])} |", row)
                self.assertIn(rub(item["profit"]).replace("-", "−"), row)

    def test_loss_making_item_is_flagged(self):
        losers = [n for n, i in self.items.items() if i["profit"] < 0]
        self.assertEqual(losers, ["LD-APRON"])
        self.assertIn("Фартук LD-APRON в минусе", self.text)


if __name__ == "__main__":
    unittest.main()
