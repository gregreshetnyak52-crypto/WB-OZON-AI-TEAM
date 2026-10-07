#!/usr/bin/env python3
"""Юнит-экономика товара на маркетплейсе (Wildberries, Ozon, Яндекс Маркет).

Считает прибыль на одну проданную (выкупленную) единицу с учётом процента
выкупа, обратной логистики, рекламы и налога. Все ставки передаются
параметрами: тарифы площадок часто меняются, поэтому берите их из личного
кабинета или последнего отчёта.

Пример:
    python3 calc.py --price 1990 --cost 650 --commission 24.5 \\
        --logistics 90 --return-logistics 50 --buyout 85 --storage 12 \\
        --ads-pct 8 --tax usn6
"""
import argparse
import sys


def unit_economics(args, price):
    buyout = args.buyout / 100
    vat = price * args.vat / (100 + args.vat) if args.vat else 0.0

    commission = price * args.commission / 100
    acquiring = price * args.acquiring / 100
    # На каждый выкуп приходится 1/buyout заказов; невыкупленные едут туда и обратно.
    logistics = (args.logistics + (1 - buyout) * args.return_logistics) / buyout
    ads = args.ads + price * args.ads_pct / 100
    expenses = (args.cost + commission + acquiring + logistics
                + args.storage + ads + args.other)

    base_income = price - vat
    if args.tax == "usn6":
        # Доход по УСН — цена продажи покупателю, а не сумма к перечислению.
        tax = base_income * args.tax_rate_usn6 / 100
    elif args.tax == "usn15":
        tax = max(base_income - expenses, 0) * args.tax_rate_usn15 / 100
    else:
        tax = 0.0

    profit = price - vat - expenses - tax
    return {
        "Цена продажи": price,
        "НДС": vat,
        "Себестоимость": args.cost,
        "Комиссия площадки": commission,
        "Эквайринг": acquiring,
        "Логистика на выкуп (с учётом невыкупов)": logistics,
        "Хранение": args.storage,
        "Реклама": ads,
        "Прочее": args.other,
        "Налог": tax,
        "Прибыль": profit,
    }


def solve_price(args, target_margin):
    """Минимальная цена, при которой маржа не ниже target_margin (%)."""
    lo, hi = 0.01, max(args.price, args.cost) * 20
    if margin(unit_economics(args, hi)) < target_margin:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if margin(unit_economics(args, mid)) >= target_margin:
            hi = mid
        else:
            lo = mid
    return hi


def margin(result):
    return result["Прибыль"] / result["Цена продажи"] * 100


def rub(value):
    return f"{value:,.0f} ₽".replace(",", " ")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--price", type=float, required=True,
                   help="цена, которую платит покупатель, после всех скидок, ₽")
    p.add_argument("--cost", type=float, required=True,
                   help="себестоимость единицы с доставкой до склада и упаковкой, ₽")
    p.add_argument("--commission", type=float, required=True,
                   help="комиссия площадки для категории, %%")
    p.add_argument("--logistics", type=float, default=0,
                   help="логистика до покупателя за единицу, ₽")
    p.add_argument("--return-logistics", type=float, default=0,
                   help="обратная логистика при невыкупе за единицу, ₽")
    p.add_argument("--buyout", type=float, default=100,
                   help="процент выкупа, %% (по умолчанию 100)")
    p.add_argument("--storage", type=float, default=0,
                   help="хранение на единицу проданного товара, ₽")
    p.add_argument("--acquiring", type=float, default=0,
                   help="эквайринг, если удерживается отдельно, %%")
    p.add_argument("--ads", type=float, default=0,
                   help="реклама на единицу, ₽")
    p.add_argument("--ads-pct", type=float, default=0,
                   help="реклама как доля от цены (ДРР), %%")
    p.add_argument("--other", type=float, default=0,
                   help="прочие расходы на единицу (маркировка, фулфилмент), ₽")
    p.add_argument("--tax", choices=["usn6", "usn15", "none"], default="usn6",
                   help="режим налога (по умолчанию usn6)")
    p.add_argument("--tax-rate-usn6", type=float, default=6, help=argparse.SUPPRESS)
    p.add_argument("--tax-rate-usn15", type=float, default=15, help=argparse.SUPPRESS)
    p.add_argument("--vat", type=float, default=0,
                   help="ставка НДС в цене, %% (0, 5, 7, 20...)")
    p.add_argument("--target-margin", type=float, default=None,
                   help="подобрать цену под целевую маржу, %%")
    return p


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)

    if not 0 < args.buyout <= 100:
        p.error("--buyout должен быть больше 0 и не больше 100")
    if args.price <= 0:
        p.error("--price должна быть больше 0")

    result = unit_economics(args, args.price)
    width = max(len(k) for k in result)
    for key, value in result.items():
        print(f"{key:<{width}}  {rub(value):>12}")
    print(f"{'Маржа от цены':<{width}}  {margin(result):>11.1f}%")
    roi = result["Прибыль"] / args.cost * 100 if args.cost else float("nan")
    print(f"{'ROI на себестоимость':<{width}}  {roi:>11.1f}%")

    breakeven = solve_price(args, 0)
    if breakeven is None:
        print("Точка безубыточности: не найдена — расходы в процентах от цены превышают 100%")
    else:
        print(f"Точка безубыточности: {rub(breakeven)}")
    if args.target_margin is not None:
        target = solve_price(args, args.target_margin)
        if target is None:
            print(f"Маржа {args.target_margin:g}% недостижима при этих ставках")
        else:
            print(f"Цена для маржи {args.target_margin:g}%: {rub(target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
