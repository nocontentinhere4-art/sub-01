"""Regression: daily growth after learned connections must keep the network runnable."""
import numpy as np
from spiking.live import LiveBrain


def test_growth_with_formed_synapses_keeps_state_and_connections():
    brain = LiveBrain(5000, None, twin=False)
    net = brain.net
    net.set_formed(np.array([0, 1]), np.array([3, 2]),
                   np.array([0.1, 0.2]), np.array([1, 2]))
    previous = net.n
    add = np.zeros(net.reg.n, dtype=np.int64)
    add[:3] = 2
    net.grow(add, seed=1)
    assert net.n == previous + 6 == len(net.v) == len(net.mu)
    assert net.formed['src'].tolist() == [0, 1]
    assert net.formed['dst'].tolist() == [3, 2]
    assert net.formed['slot_off'].tolist() == [net.n + 3, 2 * net.n + 2]
    net.run(5)
    assert np.isfinite(net.v).all()
    net.grow(add, seed=2)
    net.run(5)
    assert net.n == previous + 12 == len(net.v)
