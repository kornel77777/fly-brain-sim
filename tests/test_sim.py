"""The leaky integrate-and-fire engine: small synthetic networks, then the paper's result."""

import numpy as np
import pytest

from fly_brain_sim.sim.lif import Network, Params

P = Params()
DELAY_STEPS = round(P.t_dly / P.dt)
REFRACTORY_STEPS = round(P.t_rfc / P.dt)


def net(n: int, edges: list[tuple[int, int, int]]) -> Network:
    """Network from (pre, post, signed synapse count) edges."""
    pre, post, count = (np.array(x, dtype=np.int64) for x in zip(*edges, strict=True))
    return Network(n, pre, post, count)


def spikes_of(res, i: int) -> np.ndarray:
    return np.sort(res.spike_step[res.spike_neuron == i])


def test_network_is_silent_without_input():
    res = net(3, [(0, 1, 500), (1, 2, 500)]).run([], duration_ms=200)
    assert len(res.spike_neuron) == 0


def test_stimulated_neuron_fires_at_the_poisson_rate():
    res = net(2, [(0, 1, 1)]).run([0], duration_ms=4000, seed=1)
    assert res.rates()[0] == pytest.approx(P.r_poi, rel=0.1)


def test_strong_excitation_follows_after_the_synaptic_delay():
    res = net(2, [(0, 1, 1000)]).run([0], duration_ms=500, seed=2)
    a, b = spikes_of(res, 0), spikes_of(res, 1)
    assert len(b) > 0.8 * len(a)
    # B's first spike comes 1.8 ms (the delay) to 2.8 ms after A's: the extra time
    # is how long the voltage takes to rise. (Later lags vary: input arriving
    # while B is refractory is held in g and fires B once the period ends.)
    assert DELAY_STEPS < b[0] - a[0] <= DELAY_STEPS + 10
    # and never inside B's refractory period
    assert (np.diff(b) > REFRACTORY_STEPS).all()


def test_weak_input_stays_below_threshold():
    # A single spike through 10 synapses peaks well below the 7 mV threshold,
    # and at 150 Hz the summed input still does not reach it.
    res = net(2, [(0, 1, 10)]).run([0], duration_ms=500, seed=3)
    assert len(spikes_of(res, 1)) == 0


def test_inhibition_reduces_firing():
    # 0 excites 2; 1 inhibits 2.
    edges = [(0, 2, 60), (1, 2, -200)]
    alone = net(3, edges).run([0], duration_ms=1000, seed=4)
    inhibited = net(3, edges).run([0, 1], duration_ms=1000, seed=4)
    assert alone.rates()[2] > 0
    assert inhibited.rates()[2] < 0.5 * alone.rates()[2]


def test_silencing_removes_a_neurons_output():
    res = net(2, [(0, 1, 1000)]).run([0], duration_ms=300, seed=5, silence=[0])
    assert len(spikes_of(res, 0)) > 0 and len(spikes_of(res, 1)) == 0


def test_binning_counts_every_spike():
    res = net(2, [(0, 1, 1000)]).run([0], duration_ms=300, seed=6)
    active, counts = res.binned(bin_ms=10)
    assert counts.shape == (len(active), 30)
    assert counts.sum() == len(res.spike_neuron)


# Sugar-sensing taste neurons (right side) from the example in
# philshiu/Drosophila_brain_model. Those IDs are from FlyWire v630; 20 of the 21
# are unchanged in v783 and used here.
SUGAR_630 = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]  # fmt: skip
MN9 = 720575940660219265  # proboscis motor neuron 9


@pytest.fixture(scope="module")
def brain(db):
    return Network.from_db()


def test_sugar_neurons_activate_mn9(brain):
    # Shiu et al. 2024: activating sugar neurons drives MN9 (proboscis extension).
    index = {int(r): i for i, r in enumerate(brain.root_ids)}
    stim = [index[r] for r in SUGAR_630 if r in index]
    assert len(stim) == 20
    rates = brain.run(stim, duration_ms=1000, seed=0).rates()
    assert rates[stim].mean() == pytest.approx(P.r_poi, rel=0.1)
    assert rates[index[MN9]] > 50
    # The example notebook reports "only about 400 neurons show activity".
    assert 200 < np.count_nonzero(rates) < 800
