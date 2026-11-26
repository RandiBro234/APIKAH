export const HORIZONS = [
  { key: 'd0', label: 'AKTUAL', offsetDays: 0 },
  { key: 'd1', label: 'BESOK', offsetDays: 1 },
  { key: 'd2', label: 'LUSA', offsetDays: 2 },
  { key: 'd7', label: 'MINGGU DEPAN', offsetDays: 7 },
] as const

export type HorizonKey = (typeof HORIZONS)[number]['key']
