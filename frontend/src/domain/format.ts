/** Full dollars: $1,408,500. */
export const fmt = (n: number): string => '$' + Math.round(n).toLocaleString('en-US')

/** Compact dollars for tiles and legends: $1.41M, $156K. */
export const short = (n: number): string =>
  n >= 1e6
    ? '$' + (n / 1e6).toFixed(2).replace(/\.?0+$/, '') + 'M'
    : n >= 1e3
      ? '$' + Math.round(n / 1e3) + 'K'
      : fmt(n)

export const shortDate = (at: number, withYear = false): string =>
  new Date(at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(withYear ? { year: 'numeric' } : {}) })
