export function stripAnsi(s: string): string {
  return s.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').replace(/\x1b[()][AB012]/g, '').replace(/\x1b[^[\]]/g, '')
}

export function lastNLines(chunks: string[], n: number): string[] {
  return chunks.map(stripAnsi).join('').split('\n').map(l => l.trimEnd()).filter(l => l.length > 0).slice(-n)
}
