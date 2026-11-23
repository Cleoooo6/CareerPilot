export interface ParsedSseFrame {
  event?: string
  id?: string
  data?: string
}

export interface ParseResult {
  frames: ParsedSseFrame[]
  rest: string
}

export function parseSseBuffer(buffer: string): ParseResult {
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  const frames: ParsedSseFrame[] = []

  for (const block of blocks) {
    if (!block.trim()) continue
    const frame: ParsedSseFrame = {}
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
      if (field === 'event') frame.event = value
      else if (field === 'id') frame.id = value
      else if (field === 'data') dataLines.push(value)
    }
    if (dataLines.length > 0) frame.data = dataLines.join('\n')
    frames.push(frame)
  }

  return { frames, rest }
}