export const HORIZONS = [
  { key: 'd0', label: 'AKTUAL' },
  { key: 'd1', label: 'BESOK' },
  { key: 'd2', label: 'LUSA' },
  { key: 'd3', label: 'TULAT' },
] as const

export type HorizonKey = (typeof HORIZONS)[number]['key']
