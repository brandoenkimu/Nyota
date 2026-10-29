"""Standalone tests for analytics.mining (no Django needed).

Run:  python3 -m unittest analytics.test_mining -v
"""
import datetime as dt
import unittest

from analytics import mining as m


class RfmTests(unittest.TestCase):
    TODAY = dt.date(2026, 10, 1)

    def test_empty(self):
        self.assertEqual(m.rfm_segments([], self.TODAY), [])
        self.assertEqual(m.rfm_segments(None, self.TODAY), [])

    def test_single_customer(self):
        rows = m.rfm_segments([{'customer_id': 1, 'date': dt.date(2026, 9, 30), 'amount': 100}], self.TODAY)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['recency_days'], row['frequency'], row['monetary']), (1, 1, 100.0))
        self.assertEqual((row['r'], row['f'], row['m']), (3, 3, 3))
        self.assertEqual(row['rfm_score'], '333')
        self.assertEqual(row['segment'], 'Needs Attention')

    def test_aggregation_and_sorting(self):
        orders = [
            {'customer_id': 'a', 'date': dt.date(2026, 9, 1), 'amount': 50},
            {'customer_id': 'a', 'date': dt.date(2026, 9, 20), 'amount': 70.5},
            {'customer_id': 'b', 'date': dt.date(2026, 8, 1), 'amount': 500},
        ]
        rows = m.rfm_segments(orders, self.TODAY)
        self.assertEqual([r['customer_id'] for r in rows], ['b', 'a'])
        a = rows[1]
        self.assertEqual(a['frequency'], 2)
        self.assertEqual(a['monetary'], 120.5)
        self.assertEqual(a['recency_days'], 11)  # last order Sep 20

    def test_datetime_and_future_dates(self):
        orders = [{'customer_id': 1, 'date': dt.datetime(2026, 10, 5, 12, 0), 'amount': 10}]
        rows = m.rfm_segments(orders, dt.datetime(2026, 10, 1, 9, 0))
        self.assertEqual(rows[0]['recency_days'], 0)

    def test_segments_spread(self):
        orders = []
        # Champion: many recent big orders
        for d in range(5):
            orders.append({'customer_id': 'champ', 'date': dt.date(2026, 9, 25 + d), 'amount': 1000})
        # Lost: one old tiny order
        orders.append({'customer_id': 'lost', 'date': dt.date(2025, 1, 1), 'amount': 5})
        # Middle customers to give the quintiles some spread
        for i in range(8):
            orders.append({'customer_id': f'mid{i}', 'date': dt.date(2026, 6, 1) + dt.timedelta(days=i * 10), 'amount': 50 + i * 10})
        rows = {r['customer_id']: r for r in m.rfm_segments(orders, self.TODAY)}
        self.assertEqual(rows['champ']['segment'], 'Champions')
        self.assertEqual(rows['lost']['segment'], 'Lost')
        self.assertEqual(rows['lost']['r'], 1)
        self.assertEqual(rows['champ']['r'], 5)
        for r in rows.values():
            self.assertTrue(1 <= r['r'] <= 5 and 1 <= r['f'] <= 5 and 1 <= r['m'] <= 5)
            self.assertIn(r['segment'], {
                'Champions', 'Loyal', 'Potential Loyalist', 'New',
                'Needs Attention', 'At Risk', 'Hibernating', 'Lost'})

    def test_ties_get_equal_scores(self):
        orders = [{'customer_id': i, 'date': dt.date(2026, 9, 1), 'amount': 10} for i in range(4)]
        rows = m.rfm_segments(orders, self.TODAY)
        self.assertEqual(len({r['rfm_score'] for r in rows}), 1)
        # deterministic order for equal monetary: by customer id
        self.assertEqual([r['customer_id'] for r in rows], [0, 1, 2, 3])

    def test_new_segment(self):
        orders = [{'customer_id': 'new', 'date': dt.date(2026, 9, 30), 'amount': 20}]
        for i in range(6):
            orders.append({'customer_id': f'old{i}', 'date': dt.date(2026, 1, 1) + dt.timedelta(days=i), 'amount': 20})
            orders.append({'customer_id': f'old{i}', 'date': dt.date(2026, 2, 1) + dt.timedelta(days=i), 'amount': 20})
        rows = {r['customer_id']: r for r in m.rfm_segments(orders, self.TODAY)}
        self.assertEqual(rows['new']['segment'], 'New')


class BasketTests(unittest.TestCase):
    BASKETS = [
        ['milk', 'bread'], ['milk', 'bread', 'eggs'], ['milk', 'bread'],
        ['eggs'], ['milk'], ['tea', 'sugar'], ['milk', 'bread', 'bread'],
    ]

    def test_empty(self):
        self.assertEqual(m.market_basket([]), [])
        self.assertEqual(m.market_basket(None), [])
        self.assertEqual(m.market_basket([['a'], ['b']]), [])

    def test_pairs_both_directions(self):
        rows = m.market_basket(self.BASKETS, min_support=0.1, min_confidence=0.1, top=100)
        pairs = {(r['a'], r['b']): r for r in rows}
        self.assertIn(('milk', 'bread'), pairs)
        self.assertIn(('bread', 'milk'), pairs)
        mb = pairs[('milk', 'bread')]
        self.assertEqual(mb['count'], 4)  # duplicate bread in last basket counts once
        self.assertAlmostEqual(mb['support'], round(4 / 7, 4))
        self.assertAlmostEqual(mb['confidence'], round(4 / 5, 4))  # milk in 5 baskets
        self.assertAlmostEqual(mb['lift'], round((4 / 5) / (4 / 7), 4))
        bm = pairs[('bread', 'milk')]
        self.assertAlmostEqual(bm['confidence'], 1.0)

    def test_thresholds_and_top(self):
        rows = m.market_basket(self.BASKETS, min_support=0.5, min_confidence=0.2)
        self.assertTrue(all(r['support'] >= 0.5 for r in rows))
        self.assertEqual({(r['a'], r['b']) for r in rows}, {('milk', 'bread'), ('bread', 'milk')})
        self.assertEqual(len(m.market_basket(self.BASKETS, 0.0, 0.0, top=2)), 2)

    def test_sorted_by_lift_then_confidence(self):
        rows = m.market_basket(self.BASKETS, 0.0, 0.0, top=100)
        keys = [(-r['lift'], -r['confidence']) for r in rows]
        self.assertEqual(keys, sorted(keys))

    def test_ids_stringified(self):
        rows = m.market_basket([[1, 2], [1, 2], [3]], 0.0, 0.0)
        self.assertEqual({(r['a'], r['b']) for r in rows}, {('1', '2'), ('2', '1')})

    def test_deterministic(self):
        self.assertEqual(m.market_basket(self.BASKETS, 0, 0), m.market_basket(self.BASKETS, 0, 0))


class AbcTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(m.abc_classification([]), [])
        self.assertEqual(m.abc_classification(None), [])
        self.assertEqual(m.pareto_top([]), [])

    def test_classes(self):
        items = [{'id': 'a', 'revenue': 700}, {'id': 'b', 'revenue': 200},
                 {'id': 'c', 'revenue': 60}, {'id': 'd', 'revenue': 30}, {'id': 'e', 'revenue': 10}]
        rows = m.abc_classification(items)
        self.assertEqual([r['id'] for r in rows], ['a', 'b', 'c', 'd', 'e'])
        self.assertEqual([r['abc'] for r in rows], ['A', 'A', 'B', 'C', 'C'])
        self.assertAlmostEqual(rows[0]['share'], 0.7)
        self.assertAlmostEqual(rows[-1]['cum_share'], 1.0)

    def test_single_dominant_item_is_a(self):
        rows = m.abc_classification([{'id': 'x', 'revenue': 100}])
        self.assertEqual(rows[0]['abc'], 'A')
        self.assertEqual(rows[0]['share'], 1.0)

    def test_zero_revenue_all_c(self):
        rows = m.abc_classification([{'id': 1, 'revenue': 0}, {'id': 2, 'revenue': 0}])
        self.assertEqual([r['abc'] for r in rows], ['C', 'C'])
        self.assertEqual([r['share'] for r in rows], [0.0, 0.0])

    def test_ties_sorted_by_id(self):
        rows = m.abc_classification([{'id': 'b', 'revenue': 5}, {'id': 'a', 'revenue': 5}])
        self.assertEqual([r['id'] for r in rows], ['a', 'b'])

    def test_pareto_top(self):
        items = [{'id': i, 'revenue': r} for i, r in enumerate([500, 300, 100, 60, 40])]
        top = m.pareto_top(items, 0.8)
        self.assertEqual([r['id'] for r in top], [0, 1])
        top90 = m.pareto_top(items, 0.9)
        self.assertEqual([r['id'] for r in top90], [0, 1, 2])


class SeriesTests(unittest.TestCase):
    def test_holt_edges(self):
        self.assertEqual(m.holt_forecast([], 3), [0.0, 0.0, 0.0])
        self.assertEqual(m.holt_forecast([5], 3), [5.0, 5.0, 5.0])
        self.assertEqual(m.holt_forecast([1, 2, 3], 0), [])
        self.assertEqual(len(m.holt_forecast([1, 2, 3])), 14)

    def test_holt_trend_up(self):
        f = m.holt_forecast([10, 20, 30, 40, 50, 60, 70], horizon=5)
        self.assertEqual(len(f), 5)
        self.assertTrue(all(b > a for a, b in zip(f, f[1:])))
        self.assertGreater(f[0], 70 - 1)

    def test_holt_never_negative(self):
        f = m.holt_forecast([100, 80, 60, 40, 20, 0], horizon=10)
        self.assertTrue(all(x >= 0 for x in f))
        self.assertEqual(f[-1], 0.0)

    def test_holt_flat(self):
        f = m.holt_forecast([7, 7, 7, 7, 7], horizon=3)
        self.assertEqual(f, [7.0, 7.0, 7.0])

    def test_anomalies(self):
        self.assertEqual(m.detect_anomalies([1, 2, 3]), [])
        self.assertEqual(m.detect_anomalies([]), [])
        series = [10, 11, 9, 10, 10, 11, 9, 10, 200, 10, 9, 11]
        self.assertEqual(m.detect_anomalies(series), [8])

    def test_anomalies_no_spread(self):
        self.assertEqual(m.detect_anomalies([5, 5, 5, 5, 5, 5]), [])

    def test_anomalies_negative_spike(self):
        series = [100] * 10 + [0] + [100] * 10
        self.assertEqual(m.detect_anomalies(series), [10])

    def test_moving_average(self):
        self.assertEqual(m.moving_average([], 3), [])
        self.assertEqual(m.moving_average([2, 4, 6, 8], 2), [2.0, 3.0, 5.0, 7.0])
        self.assertEqual(m.moving_average([1, 2, 3], 7), [1.0, 1.5, 2.0])
        self.assertEqual(m.moving_average([1, 2, 3], 0), [1.0, 2.0, 3.0])

    def test_growth_rate(self):
        self.assertEqual(m.growth_rate(150, 100), 50.0)
        self.assertEqual(m.growth_rate(50, 100), -50.0)
        self.assertIsNone(m.growth_rate(10, 0))
        self.assertIsNone(m.growth_rate(10, None))
        self.assertEqual(m.growth_rate(0, 100), -100.0)


class SentimentTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(m.sentiment_score(''), 0.0)
        self.assertEqual(m.sentiment_score(None), 0.0)
        self.assertEqual(m.sentiment_label(0.0), 'neutral')
        self.assertEqual(m.sentiment_label(None), 'neutral')

    def test_positive_negative(self):
        self.assertGreater(m.sentiment_score('Great quality, fast delivery, love it!'), 0.5)
        self.assertLess(m.sentiment_score('Terrible. Fake and broken, want a refund'), -0.5)

    def test_swahili(self):
        self.assertEqual(m.sentiment_label(m.sentiment_score('Bidhaa nzuri sana')), 'positive')
        self.assertEqual(m.sentiment_label(m.sentiment_score('Huduma mbaya')), 'negative')

    def test_negation(self):
        self.assertLess(m.sentiment_score('not good'), 0)
        self.assertGreater(m.sentiment_score('not bad'), 0)
        self.assertLess(m.sentiment_score("it wasn't great"), 0)

    def test_intensifier(self):
        self.assertGreater(m.sentiment_score('very good'), m.sentiment_score('good'))

    def test_bounds_and_labels(self):
        score = m.sentiment_score('excellent ' * 50)
        self.assertLessEqual(score, 1.0)
        self.assertEqual(m.sentiment_label(0.5), 'positive')
        self.assertEqual(m.sentiment_label(-0.5), 'negative')
        self.assertEqual(m.sentiment_label(0.1), 'neutral')
        self.assertEqual(m.sentiment_score('the parcel arrived on tuesday'), 0.0)

    def test_curly_apostrophe(self):
        self.assertLess(m.sentiment_score('it wasn’t good'), 0)


if __name__ == '__main__':
    unittest.main()
