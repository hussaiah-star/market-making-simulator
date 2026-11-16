"""
Market-making simulator.

A market maker quotes a bid (price it will buy at) and an ask (price it will
sell at) around the current mid price. It earns the spread when both sides
trade, but every one-sided fill leaves it holding inventory, and inventory
loses money if the price moves against it.

This module compares two quoting strategies over many simulated trading days:

  1. Symmetric: always quote the same distance either side of the mid price.
  2. Inventory-aware: shift both quotes away from the side where inventory is
     building up, following Avellaneda and Stoikov (2008), "High-frequency
     trading in a limit order book", Quantitative Finance 8(3).

Model assumptions (kept deliberately simple):
  * The mid price follows a random walk: each step it moves by
    sigma * sqrt(dt) * Z, where Z is a standard normal draw.
  * Market orders arrive at random. The chance that a quote placed a distance
    d from the mid gets hit in one step is A * exp(-k * d) * dt, so quotes
    further from the mid trade less often.
  * One unit trades per fill. No fees, no latency, no competing market makers.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class MarketParams:
    s0: float = 100.0      # starting mid price
    sigma: float = 2.0     # price volatility per unit of time
    T: float = 1.0         # length of the trading day
    dt: float = 0.005      # time step (200 steps per day)
    A: float = 140.0       # order arrival intensity at the mid
    k: float = 1.5         # how fast fill probability decays with distance


def as_quotes(s, q, t, gamma, p: MarketParams):
    """Avellaneda-Stoikov quotes.

    reservation price r = s - q * gamma * sigma^2 * (T - t)
        Long inventory (q > 0) pushes r below the mid, so the market maker
        sells more readily and buys less readily until inventory comes back
        toward zero.
    total spread = gamma * sigma^2 * (T - t) + (2 / gamma) * ln(1 + gamma / k)
    """
    tau = p.T - t
    r = s - q * gamma * p.sigma ** 2 * tau
    spread = gamma * p.sigma ** 2 * tau + (2.0 / gamma) * np.log(1.0 + gamma / p.k)
    return r - spread / 2.0, r + spread / 2.0


def symmetric_quotes(s, q, t, gamma, p: MarketParams):
    """Same total spread as the inventory-aware strategy, centred on the mid.

    Using the same spread makes the comparison fair: the only difference
    between the two strategies is whether quotes react to inventory.
    """
    tau = p.T - t
    spread = gamma * p.sigma ** 2 * tau + (2.0 / gamma) * np.log(1.0 + gamma / p.k)
    return s - spread / 2.0, s + spread / 2.0


def simulate_day(strategy, gamma, p: MarketParams, rng, quote_p: MarketParams = None):
    """Run one trading day. Returns final P&L, final inventory and the path.

    quote_p is what the market maker *believes* the market looks like. By
    default it equals p, the true market. Passing a different quote_p tests
    what happens when the model is wrong, for example when volatility jumps
    and the quotes have not been recalibrated.
    """
    quote_p = quote_p or p
    n = int(round(p.T / p.dt))
    s, cash, q = p.s0, 0.0, 0
    inv_path = np.empty(n)
    for i in range(n):
        t = i * p.dt
        bid, ask = strategy(s, q, t, gamma, quote_p)
        # chance each quote is hit this step
        p_bid = min(1.0, p.A * np.exp(-p.k * (s - bid)) * p.dt)
        p_ask = min(1.0, p.A * np.exp(-p.k * (ask - s)) * p.dt)
        if rng.random() < p_bid:      # someone sells to us at our bid
            q += 1
            cash -= bid
        if rng.random() < p_ask:      # someone buys from us at our ask
            q -= 1
            cash += ask
        s += p.sigma * np.sqrt(p.dt) * rng.standard_normal()
        inv_path[i] = q
    pnl = cash + q * s                # mark remaining inventory at the final mid
    return pnl, q, inv_path


def run(strategy, gamma, p: MarketParams, n_days=1000, seed=0, quote_p: MarketParams = None):
    """Simulate many days and summarise the P&L distribution."""
    rng = np.random.default_rng(seed)
    pnls, invs = np.empty(n_days), np.empty(n_days)
    for d in range(n_days):
        pnls[d], invs[d], _ = simulate_day(strategy, gamma, p, rng, quote_p)
    return {
        "mean_pnl": float(pnls.mean()),
        "std_pnl": float(pnls.std(ddof=1)),
        "ratio": float(pnls.mean() / pnls.std(ddof=1)),
        "mean_abs_inventory": float(np.abs(invs).mean()),
        "pnls": pnls,
        "inventories": invs,
    }
