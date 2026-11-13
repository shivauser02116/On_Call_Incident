export function Spark({ points, tone = 'bad' }: { points: number[]; tone?: 'bad' | 'accent' }) {
  const max = Math.max(...points)
  const min = Math.min(...points)
  const pts = points.map((p, i) => `${(i / (points.length - 1)) * 100},${30 - ((p - min) / (max - min || 1)) * 26}`).join(' ')
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className={`h-10 w-full ${tone === 'bad' ? 'text-bad' : 'text-accent'}`} aria-hidden>
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

const scenarioProfiles: Record<string, { before: number[]; after: number[] }> = {
  connection_pool_leak: {
    before: [2900, 3050, 3120, 3080, 3150, 3200, 3110, 3180],
    after: [210, 110, 75, 62, 58, 60, 59, 58],
  },
  memory_leak: {
    before: [1680, 1720, 1760, 1800, 1820, 1850, 1830, 1860],
    after: [620, 530, 505, 490, 488, 485, 487, 485],
  },
  third_party_outage: {
    before: [4900, 5000, 4950, 5000, 5020, 4980, 5000, 5010],
    after: [320, 180, 140, 130, 125, 128, 126, 125],
  },
  config_change_flag: {
    before: [1080, 1140, 1110, 1130, 1100, 1150, 1120, 1125],
    after: [180, 120, 105, 95, 92, 94, 93, 92],
  },
  ambiguous_escalate: {
    before: [1400, 1950, 1520, 1980, 1600, 2010, 1680, 1850],
    after: [340, 240, 200, 180, 175, 178, 176, 175],
  },
  bad_deploy_slow_queries: {
    before: [2290, 2410, 2330, 2380, 2300, 2420, 2340, 2370],
    after: [310, 220, 200, 190, 185, 195, 190, 188],
  },
}

// Response time during the practice run: dynamically adapts to the selected scenario
export function PracticeChart({ scenarioId }: { scenarioId?: string }) {
  const profile = (scenarioId && scenarioProfiles[scenarioId]) || scenarioProfiles.bad_deploy_slow_queries
  const before = profile.before
  const after = profile.after
  const all = [...before, ...after]
  const maxVal = Math.max(...all, 100)
  const x = (i: number) => (i / (all.length - 1)) * 400
  const y = (v: number) => 112 - (v / (maxVal * 1.08)) * 100
  const line = all.map((v, i) => `${i === 8 ? 'L' : i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const area = `${line} L400,112 L0,112 Z`
  const mid = (x(7) + x(8)) / 2

  return (
    <div>
      <div className="relative">
        <svg
          viewBox="0 0 400 120"
          preserveAspectRatio="none"
          className="aspect-[4/1] max-h-40 min-h-24 w-full"
          role="img"
          aria-label={`Practice run metric improved from ${before[before.length - 1]} to ${after[after.length - 1]} after the fix`}
        >
          <defs>
            <linearGradient id="pc" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="#8b93ff" stopOpacity="0.28" />
              <stop offset="1" stopColor="#8b93ff" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[20, 60, 100].map((g) => (
            <line key={g} x1="0" x2="400" y1={g} y2={g} stroke="#1f2837" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          <path d={area} fill="url(#pc)" />
          <path d={line} fill="none" stroke="#8b93ff" strokeWidth="2.25" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
          <line x1={mid} x2={mid} y1="0" y2="112" stroke="#8b95a9" strokeDasharray="3 4" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div className="mt-2 flex text-[12px] text-faint">
        <span className="flex-1">Before fix ({before[before.length - 1]})</span>
        <span className="flex-1 text-right">After fix ({after[after.length - 1]})</span>
      </div>
    </div>
  )
}
