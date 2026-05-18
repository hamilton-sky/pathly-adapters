import type { Terminal as XTerm } from '@xterm/xterm'
import type { FitAddon } from '@xterm/addon-fit'
import type { TerminalTab } from '../../store/terminalStore'

export interface TabInstance {
  xterm: XTerm
  fitAddon: FitAddon
  container: HTMLDivElement | null
}

export type { TerminalTab }
