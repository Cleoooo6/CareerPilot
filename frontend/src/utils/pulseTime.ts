export const PULSE_TIME_ZONE = 'Asia/Shanghai'

const formatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: PULSE_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatPulseDate(
  value: string | null,
  now: number = Date.now(),
): string {
  if (!value) return '发布时间缺失'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '发布时间待核实'
  if (date.getTime() > now) return '发布时间待核实（晚于当前时间）'
  return formatter.format(date)
}