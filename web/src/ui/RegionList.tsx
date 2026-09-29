import { useMemo } from 'react'
import { REGION_GROUPS, regionInfo, type RegionInfo } from '../content'
import { useStore } from '../store'

/** All brain regions, grouped by system, each with a short explanation. */
export function RegionList() {
  const regions = useStore((s) => s.regions)
  const selectRegion = useStore((s) => s.selectRegion)

  const groups = useMemo(() => {
    const byGroup = new Map<string, RegionInfo[]>()
    for (const r of regions?.regions ?? []) {
      const info = regionInfo(r.name)
      byGroup.set(info.group.id, [...(byGroup.get(info.group.id) ?? []), info])
    }
    return REGION_GROUPS.map((g) => ({ group: g, regions: byGroup.get(g.id) ?? [] })).filter(
      (g) => g.regions.length > 0,
    )
  }, [regions])

  if (!regions) {
    return (
      <section>
        <p className="muted small">
          Region shapes are not available. Build them with scripts/build_regions.py.
        </p>
      </section>
    )
  }

  return (
    <section>
      <p className="explain">
        Neuropils are dense tangles of branches where neurons connect. They are grouped here by
        the system they belong to. Click one to see what it does and where its signals go.
      </p>
      {groups.map(({ group, regions: members }) => (
        <details key={group.id} className="group">
          <summary>
            <span className="dot" style={{ background: group.color }} />
            <span className="grow">{group.label}</span>
            <span className="small muted">{members.length}</span>
          </summary>
          <p className="small">{group.description}</p>
          <div className="chips">
            {members
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((r) => (
                <button key={r.code} className="chip" onClick={() => selectRegion(r.code)}>
                  {r.name}
                </button>
              ))}
          </div>
        </details>
      ))}
    </section>
  )
}
