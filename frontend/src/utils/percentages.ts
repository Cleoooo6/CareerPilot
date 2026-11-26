export interface PercentageItem {
  name: string
  count: number
}

export function allocatePercentages(
  items: PercentageItem[],
): Record<string, number> {
  const total = items.reduce((sum, item) => sum + item.count, 0)
  if (!total) return {}
  const raw = items.map((item) => (item.count / total) * 100)
  const whole = raw.map(Math.floor)
  let left = 100 - whole.reduce((sum, value) => sum + value, 0)
  const order = raw
    .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
    .sort((a, b) => b.fraction - a.fraction || a.index - b.index)
  for (const item of order) {
    if (left <= 0) break
    whole[item.index] += 1
    left -= 1
  }
  return Object.fromEntries(items.map((item, index) => [item.name, whole[index]]))
}