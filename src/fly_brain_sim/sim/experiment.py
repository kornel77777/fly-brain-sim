"""Stimulation experiments for the viewer: presets, target resolution, summaries."""

from dataclasses import dataclass

import duckdb
import numpy as np

from fly_brain_sim.sim.lif import Network, Params

# Sugar-sensing taste neurons (right) from the example in philshiu/Drosophila_brain_model.
# They are FlyWire v630 IDs; 20 of the 21 are unchanged in v783.
SUGAR_630 = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]  # fmt: skip

MAX_STIMULATED = 300  # larger groups (e.g. a whole region) are sampled down


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    description: str
    sql: str  # returns root_id


PRESETS = [
    Preset(
        "sugar",
        "Sweet taste",
        "Sugar-sensing taste neurons on the right side of the proboscis, the set used in "
        "Shiu et al. 2024. In their model, activating them drove MN9, a motor neuron that "
        "extends the proboscis to feed. Watch activity travel through the gnathal ganglia "
        "to MN9.",
        "select root_id from neurons where root_id in (" + ", ".join(map(str, SUGAR_630)) + ")",
    ),
    Preset(
        "bitter",
        "Bitter taste",
        "Bitter-sensing taste neurons on the right side. Bitter taste makes flies stop "
        "feeding. Compare with the sweet preset: which neurons respond to both, and does "
        "MN9 fire?",
        "select root_id from neurons "
        "where class = 'gustatory' and sub_class = 'bitter' and side = 'right'",
    ),
    Preset(
        "pheromone",
        "Pheromone smell",
        "Olfactory receptor neurons of the right antenna that detect cis-vaccenyl acetate, "
        "a male pheromone. They all converge on one glomerulus (DA1) of the antennal lobe; "
        "projection neurons carry the signal on to the lateral horn and mushroom body.",
        "select root_id from neurons where cell_type = 'ORN_DA1' and side = 'right'",
    ),
    Preset(
        "hearing",
        "Hearing",
        "Johnston's organ neurons (types A and B) in the right antenna, which respond to "
        "sound and vibration. They feed the AMMC and wedge, the first stages of processing "
        "courtship song.",
        "select root_id from neurons where cell_type in ('JO-A', 'JO-B') and side = 'right'",
    ),
]
PRESETS_BY_ID = {p.id: p for p in PRESETS}


def resolve_target(con: duckdb.DuckDBPyConnection, target: dict) -> tuple[str, list[int]]:
    """(label, root IDs) for a target description from the viewer."""
    kind = target.get("kind")
    if kind == "preset":
        preset = PRESETS_BY_ID.get(target.get("id", ""))
        if preset is None:
            raise ValueError(f"unknown preset {target.get('id')!r}")
        ids = [r[0] for r in con.execute(preset.sql).fetchall()]
        return preset.label, ids
    if kind == "neurons":
        ids = [int(r) for r in target.get("root_ids", [])]
        return (f"{len(ids)} neuron{'s' if len(ids) != 1 else ''}", ids)
    if kind == "cell_type":
        cell_type = target.get("cell_type")
        side = target.get("side")
        sql = "select root_id from neurons where cell_type = ?"
        params: list = [cell_type]
        if side:
            sql += " and side = ?"
            params.append(side)
        ids = [r[0] for r in con.execute(sql, params).fetchall()]
        return (f"{cell_type}" + (f" ({side})" if side else ""), ids)
    if kind == "region":
        region = target.get("region")
        ids = [
            r[0]
            for r in con.execute(
                "select root_id from neuron_home_neuropil where home_neuropil = ?", [region]
            ).fetchall()
        ]
        return f"neurons of {region}", ids
    raise ValueError(f"unknown target kind {kind!r}")


def run_experiment(
    net: Network,
    con: duckdb.DuckDBPyConnection,
    overview_root_ids: np.ndarray,
    root_ids: list[int],
    rate_hz: float = 150.0,
    duration_ms: float = 300.0,
    bin_ms: float = 5.0,
    seed: int = 0,
    top_n: int = 25,
) -> dict:
    """Stimulate `root_ids` and summarise the response for display.

    Neuron indices in the result refer to the overview order (neurons sorted by
    root ID), the same indices the viewer uses for colouring.
    """
    model_index = {int(r): i for i, r in enumerate(net.root_ids)}
    in_model = sorted({model_index[r] for r in root_ids if r in model_index})
    n_requested = len(set(root_ids))
    sampled = False
    if len(in_model) > MAX_STIMULATED:
        rng = np.random.default_rng(seed)
        in_model = sorted(rng.choice(in_model, MAX_STIMULATED, replace=False).tolist())
        sampled = True

    params = Params(r_poi=rate_hz)
    res = net.run(np.array(in_model, dtype=np.int64), duration_ms, params, seed=seed)
    active_model, counts = res.binned(bin_ms)
    rates = counts.sum(axis=1) / (res.duration_ms / 1000.0)

    def to_overview(model_idx: np.ndarray) -> np.ndarray:
        return np.searchsorted(overview_root_ids, net.root_ids[model_idx]).astype(np.int64)

    active = to_overview(active_model)
    stimulated = to_overview(np.array(in_model, dtype=np.int64))
    first_bin = np.argmax(counts > 0, axis=1) if len(counts) else np.array([], dtype=np.int64)

    # Spikes per home region and time bin (the "which parts light up" view).
    active_ids = [int(r) for r in net.root_ids[active_model]]
    home = con.execute(
        "select a.k - 1, h.home_neuropil "
        "from unnest(?::BIGINT[]) with ordinality as a(root_id, k) "
        "join neuron_home_neuropil h using (root_id)",
        [active_ids],
    ).fetchall()
    # Share of spikes fired by Kenyon cells. The model treats their many
    # Kenyon-cell-to-Kenyon-cell synapses as excitatory, so once activity reaches
    # the mushroom body it tends to spread and saturate; the viewer flags this.
    kc = con.execute(
        "select a.k - 1 from unnest(?::BIGINT[]) with ordinality as a(root_id, k) "
        "join neurons n using (root_id) where n.cell_type like 'KC%'",
        [active_ids],
    ).fetchall()
    kc_spikes = int(counts[[k for (k,) in kc]].sum()) if kc else 0

    region_names = sorted({h for _, h in home})
    region_counts = np.zeros((len(region_names), counts.shape[1]), dtype=np.int64)
    pos = {name: i for i, name in enumerate(region_names)}
    for k, h in home:
        region_counts[pos[h]] += counts[k]

    # Most active responding (not stimulated) neurons.
    stim_set = set(stimulated.tolist())
    order = np.argsort(-rates, kind="stable")
    top_rows = [k for k in order if int(active[k]) not in stim_set][:top_n]
    info = {}
    if top_rows:
        ids = [int(net.root_ids[active_model[k]]) for k in top_rows]
        placeholders = ", ".join("?" for _ in ids)
        for row in con.execute(
            f"select root_id, cell_type, super_class, side, nt_type from neurons "
            f"where root_id in ({placeholders})",
            ids,
        ).fetchall():
            info[row[0]] = row[1:]
    top = []
    for k in top_rows:
        rid = int(net.root_ids[active_model[k]])
        cell_type, super_class, side, nt_type = info.get(rid, (None,) * 4)
        top.append(
            {
                "root_id": str(rid),
                "index": int(active[k]),
                "cell_type": cell_type,
                "super_class": super_class,
                "side": side,
                "nt_type": nt_type,
                "rate_hz": round(float(rates[k]), 1),
                "first_spike_ms": round(float(first_bin[k] * bin_ms), 1),
            }
        )

    return {
        "n_requested": n_requested,
        "n_not_in_model": n_requested - len(set(root_ids) & set(model_index)),
        "sampled": sampled,
        "stimulated": stimulated.tolist(),
        "rate_hz": rate_hz,
        "duration_ms": res.duration_ms,
        "bin_ms": bin_ms,
        "n_bins": int(counts.shape[1]),
        "n_spikes": int(len(res.spike_neuron)),
        "kenyon_cell_share": round(kc_spikes / max(1, len(res.spike_neuron)), 3),
        "active": active.tolist(),
        "counts": counts.reshape(-1).tolist(),
        "top": top,
        "regions": {"names": region_names, "counts": region_counts.reshape(-1).tolist()},
    }
