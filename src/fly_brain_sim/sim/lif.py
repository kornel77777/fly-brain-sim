"""Whole-brain leaky integrate-and-fire model of Shiu et al. 2024 (Nature 634:210).

A re-implementation of their Brian2 model (philshiu/Drosophila_brain_model,
model.py) in numba, with the same equations, parameters and update order:

    dv/dt = (v_0 - v + g) / t_mbr      (frozen while refractory)
    dg/dt = -g / tau                   (frozen while refractory)
    spike when v > v_th; then v = v_rst, g = 0, refractory for t_rfc
    each presynaptic spike adds w = w_syn * (signed synapse count) to g after t_dly
    stimulated neurons get Poisson input at r_poi that adds w_syn * f_poi to v
    (enough to trigger a spike) and have no refractory period

v and g are integrated exactly over each dt (Brian2's "linear" method). Per step
the order follows Brian2's schedule: state update, threshold, synaptic and
Poisson input, reset. Weights come from Connectivity_783.parquet: the synapse
count of each pair, signed -1 for GABA/glutamate and +1 otherwise.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numba
import numpy as np

from fly_brain_sim.data.paths import DB_PATH


@dataclass(frozen=True)
class Params:
    v_0: float = -52.0  # mV, resting potential
    v_rst: float = -52.0  # mV, reset potential
    v_th: float = -45.0  # mV, spike threshold
    t_mbr: float = 20.0  # ms, membrane time constant
    tau: float = 5.0  # ms, synaptic time constant
    t_rfc: float = 2.2  # ms, refractory period
    t_dly: float = 1.8  # ms, synaptic delay
    w_syn: float = 0.275  # mV per synapse
    r_poi: float = 150.0  # Hz, Poisson input rate for stimulated neurons
    f_poi: float = 250.0  # Poisson input weight, in units of w_syn
    dt: float = 0.1  # ms, Brian2's default time step


DEFAULT_PARAMS = Params()


@dataclass
class SimResult:
    spike_neuron: np.ndarray  # int32, model index of each spike
    spike_step: np.ndarray  # int32, time step of each spike
    n_neurons: int
    n_steps: int
    dt: float  # ms

    @property
    def duration_ms(self) -> float:
        return self.n_steps * self.dt

    def rates(self) -> np.ndarray:
        """Firing rate of every neuron, in Hz."""
        counts = np.bincount(self.spike_neuron, minlength=self.n_neurons)
        return counts / (self.duration_ms / 1000.0)

    def binned(self, bin_ms: float) -> tuple[np.ndarray, np.ndarray]:
        """(active neurons, spike counts per active neuron and time bin)."""
        bin_steps = max(1, round(bin_ms / self.dt))
        n_bins = math.ceil(self.n_steps / bin_steps)
        active, inverse = np.unique(self.spike_neuron, return_inverse=True)
        counts = np.zeros((len(active), n_bins), dtype=np.int32)
        np.add.at(counts, (inverse, self.spike_step // bin_steps), 1)
        return active, counts


class Network:
    """The connectome as a sparse weight matrix, ready to simulate."""

    def __init__(self, n: int, pre: np.ndarray, post: np.ndarray, count: np.ndarray):
        order = np.argsort(pre, kind="stable")
        self.n = n
        self.indptr = np.zeros(n + 1, dtype=np.int64)
        np.cumsum(np.bincount(pre, minlength=n), out=self.indptr[1:])
        self.post = post[order].astype(np.int32)
        self.count = count[order].astype(np.float64)  # signed synapse counts

    @classmethod
    def from_db(cls, db_path: Path = DB_PATH) -> "Network":
        """Build from the Shiu tables; also returns root IDs by model index."""
        with duckdb.connect(db_path, read_only=True) as con:
            con.execute("set enable_progress_bar = false")
            ids = con.execute("select root_id from shiu_neurons order by shiu_index").fetchnumpy()
            edges = con.execute(
                "select pre_shiu_index, post_shiu_index, signed_syn_count from shiu_connections"
            ).fetchnumpy()
        net = cls(
            len(ids["root_id"]),
            edges["pre_shiu_index"].astype(np.int64),
            edges["post_shiu_index"].astype(np.int64),
            edges["signed_syn_count"],
        )
        net.root_ids = np.asarray(ids["root_id"], dtype=np.int64)
        return net

    def run(
        self,
        stimulate: np.ndarray,
        duration_ms: float = 1000.0,
        params: Params = DEFAULT_PARAMS,
        seed: int = 0,
        silence: np.ndarray | None = None,
    ) -> SimResult:
        """Simulate one trial with Poisson input to the `stimulate` neurons (model indices)."""
        p = params
        n_steps = round(duration_ms / p.dt)
        stim = np.zeros(self.n, dtype=np.bool_)
        stim[np.asarray(stimulate, dtype=np.int64)] = True
        silent = np.zeros(self.n, dtype=np.bool_)
        if silence is not None:
            silent[np.asarray(silence, dtype=np.int64)] = True
        a = math.exp(-p.dt / p.t_mbr)
        b = math.exp(-p.dt / p.tau)
        c = p.tau / (p.tau - p.t_mbr) * (b - a)
        neurons, steps = _simulate(
            self.indptr,
            self.post,
            self.count * p.w_syn,
            stim,
            silent,
            n_steps,
            a,
            b,
            c,
            p.v_th - p.v_0,
            p.v_rst - p.v_0,
            round(p.t_rfc / p.dt),
            round(p.t_dly / p.dt),
            p.r_poi * p.dt / 1000.0,
            p.w_syn * p.f_poi,
            seed,
        )
        return SimResult(neurons, steps, self.n, n_steps, p.dt)


# Below this (mV), a neuron's v - v_0 and g count as fully decayed and it drops out
# of the active set; 70,000x below the 7 mV distance to threshold.
QUIET_MV = 1e-4


@numba.njit(cache=True, nogil=True)
def _simulate(
    indptr, post, weight, stim, silent, n_steps, a, b, c, u_th, u_rst,
    rfc_steps, dly_steps, p_poi, poi_amp, seed,
):  # fmt: skip
    # u = v - v_0 (so rest is 0); g in mV. Only neurons that received input and
    # have not decayed back to rest are updated ("active"); the rest sit at u = g = 0.
    np.random.seed(seed)
    n = len(stim)
    u = np.zeros(n)
    g = np.zeros(n)
    free_at = np.zeros(n, dtype=np.int64)  # first step at which a neuron is not refractory
    stim_idx = np.flatnonzero(stim)
    is_active = np.zeros(n, dtype=np.bool_)
    active = np.empty(n, dtype=np.int64)
    n_active = 0

    cap = 1 << 16
    rec_n = np.empty(cap, dtype=np.int32)
    rec_t = np.empty(cap, dtype=np.int32)
    count = 0
    deliver = 0  # next recorded spike to deliver

    for s in range(n_steps):
        first = count
        # state update + threshold, compacting the active list as neurons go quiet
        kept = 0
        for k in range(n_active):
            i = active[k]
            if s >= free_at[i]:
                ui = a * u[i] + c * g[i]
                u[i] = ui
                g[i] = b * g[i]
                if ui > u_th:
                    if count == cap:
                        cap *= 2
                        new_n = np.empty(cap, dtype=np.int32)
                        new_t = np.empty(cap, dtype=np.int32)
                        new_n[:count] = rec_n[:count]
                        new_t[:count] = rec_t[:count]
                        rec_n = new_n
                        rec_t = new_t
                    rec_n[count] = i
                    rec_t[count] = s
                    count += 1
                elif abs(ui) < QUIET_MV and abs(g[i]) < QUIET_MV:
                    u[i] = 0.0
                    g[i] = 0.0
                    is_active[i] = False
                    continue
            active[kept] = i
            kept += 1
        n_active = kept
        # synaptic input from spikes emitted dly_steps ago
        while deliver < count and rec_t[deliver] <= s - dly_steps:
            j = rec_n[deliver]
            if not silent[j]:
                for k in range(indptr[j], indptr[j + 1]):
                    t = post[k]
                    g[t] += weight[k]
                    if not is_active[t]:
                        is_active[t] = True
                        active[n_active] = t
                        n_active += 1
            deliver += 1
        # Poisson input to stimulated neurons
        for i in stim_idx:
            if np.random.random() < p_poi:
                u[i] += poi_amp
                if not is_active[i]:
                    is_active[i] = True
                    active[n_active] = i
                    n_active += 1
        # reset neurons that spiked this step
        for k in range(first, count):
            i = rec_n[k]
            u[i] = u_rst
            g[i] = 0.0
            free_at[i] = s + 1 if stim[i] else s + 1 + rfc_steps
    return rec_n[:count].copy(), rec_t[:count].copy()
