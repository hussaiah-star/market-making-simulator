"""Sanity checks. Run with: python -m unittest test_simulator"""
import unittest
import numpy as np
from simulator import MarketParams, as_quotes, symmetric_quotes, simulate_day, run

P = MarketParams()


class QuoteTests(unittest.TestCase):
    def test_flat_inventory_quotes_are_centred(self):
        bid, ask = as_quotes(100.0, 0, 0.0, 0.1, P)
        self.assertAlmostEqual((bid + ask) / 2, 100.0)

    def test_long_inventory_shifts_quotes_down(self):
        bid0, ask0 = as_quotes(100.0, 0, 0.0, 0.1, P)
        bid5, ask5 = as_quotes(100.0, 5, 0.0, 0.1, P)
        self.assertLess(bid5, bid0)
        self.assertLess(ask5, ask0)

    def test_symmetric_ignores_inventory(self):
        self.assertEqual(symmetric_quotes(100.0, 0, 0.3, 0.1, P), symmetric_quotes(100.0, 9, 0.3, 0.1, P))

    def test_same_spread_both_strategies(self):
        b1, a1 = as_quotes(100.0, 3, 0.5, 0.1, P)
        b2, a2 = symmetric_quotes(100.0, 3, 0.5, 0.1, P)
        self.assertAlmostEqual(a1 - b1, a2 - b2)


class SimulationTests(unittest.TestCase):
    def test_reproducible_with_seed(self):
        r1 = simulate_day(as_quotes, 0.1, P, np.random.default_rng(42))
        r2 = simulate_day(as_quotes, 0.1, P, np.random.default_rng(42))
        self.assertEqual(r1[0], r2[0])

    def test_inventory_aware_is_less_risky(self):
        sym = run(symmetric_quotes, 0.1, P, n_days=300, seed=5)
        inv = run(as_quotes, 0.1, P, n_days=300, seed=5)
        self.assertLess(inv["std_pnl"], sym["std_pnl"])
        self.assertLess(inv["mean_abs_inventory"], sym["mean_abs_inventory"])


if __name__ == "__main__":
    unittest.main()
