"""Skeleton parsing and simplification on small synthetic trees (no data needed)."""

import numpy as np
import pytest

from fly_brain_sim.data.skeletons import Skeleton, parse_swc, resample


def skeleton(xyz, parent) -> Skeleton:
    n = len(parent)
    return Skeleton(
        root_id=1,
        xyz=np.asarray(xyz, dtype=np.float32),
        parent=np.asarray(parent, dtype=np.int32),
        radius=np.ones(n, np.float32),
        label=np.zeros(n, np.int8),
    )


def line(n: int, spacing: float, start=(0.0, 0.0, 0.0), axis: int = 0):
    xyz = np.tile(np.asarray(start, dtype=np.float64), (n, 1))
    xyz[:, axis] += np.arange(n) * spacing
    return xyz


def test_parse_swc_converts_to_zero_based_parents():
    swc = b"""# comment
# PointNo Label X Y Z Radius Parent
1 1 10.0 20.0 30.0 5 -1
2 0 11.0 20.0 30.0 1 1
3 6 12.0 20.0 30.0 1 2
"""
    sk = parse_swc(swc, 42)
    assert sk.parent.tolist() == [-1, 0, 1]
    assert sk.xyz.dtype == np.float32
    assert sk.xyz[2].tolist() == [12.0, 20.0, 30.0]
    assert sk.label.tolist() == [1, 0, 6]


def test_parse_swc_rejects_non_sequential_ids():
    swc = b"1 1 0 0 0 1 -1\n3 0 1 0 0 1 1\n"
    with pytest.raises(ValueError):
        parse_swc(swc, 42)


def test_straight_line_is_sampled_every_step():
    # 100 um of cable, 1 um apart; step 20 um -> root, 4 intermediate nodes, tip.
    sk = skeleton(line(101, 1000.0), [-1, *range(100)])
    kept, parent = resample(sk, 20_000)
    assert kept.tolist() == [0, 20, 40, 60, 80, 100]
    assert parent.tolist() == [-1, 0, 1, 2, 3, 4]


def test_short_twigs_are_pruned_and_long_branches_kept():
    trunk = line(81, 1000.0)  # 80 um along x, nodes 0..80
    twig = line(5, 1000.0, start=(25_000, 1000, 0), axis=1)  # 5 um twig off node 25: 81..85
    branch = line(30, 1000.0, start=(40_000, 0, 1000), axis=2)  # 30 um off node 40: 86..115
    xyz = np.vstack([trunk, twig, branch])
    parent = [-1, *range(80)]
    parent += [25, *range(81, 85)]
    parent += [40, *range(86, 115)]
    sk = skeleton(xyz, parent)

    kept, new_parent = resample(sk, 20_000)
    kept = kept.tolist()
    assert not set(range(81, 86)) & set(kept)  # twig gone
    assert {0, 40, 80, 115} <= set(kept)  # root, branch point and both tips kept
    assert all(p < i for i, p in enumerate(new_parent) if p >= 0)  # parents first


def test_side_branch_shorter_than_main_path_is_the_one_pruned():
    # A 10 um tail past a branch point is a twig when the other side is longer.
    trunk = line(51, 1000.0)  # 0..50
    branch = line(40, 1000.0, start=(40_000, 0, 1000), axis=2)  # 51..90 off node 40
    parent = [-1, *range(50), 40, *range(51, 90)]
    kept, _ = resample(skeleton(np.vstack([trunk, branch]), parent), 20_000)
    assert 90 in kept.tolist() and 50 not in kept.tolist()


def test_each_tree_of_a_forest_keeps_its_root():
    a = line(30, 1000.0)
    b = line(30, 1000.0, start=(0, 100_000, 0))
    parent = [-1, *range(29), -1, *range(30, 59)]
    kept, new_parent = resample(skeleton(np.vstack([a, b]), parent), 20_000)
    assert (new_parent == -1).sum() == 2
    assert {0, 30} <= set(kept.tolist())


def test_tiny_neuron_reduces_to_root_and_tip():
    sk = skeleton(line(5, 1000.0), [-1, 0, 1, 2, 3])
    kept, parent = resample(sk, 20_000)
    assert kept.tolist() == [0, 4]
    assert parent.tolist() == [-1, 0]
