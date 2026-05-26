import { ipcMain } from 'electron'
import type { BrowserWindow } from 'electron'
import { PlaywrightExecutor } from '../automation/playwrightExecutor'
import type { AutomationStep } from '../automation/playwrightExecutor'

let executor: PlaywrightExecutor | null = null

export function registerAutomationHandlers(win: BrowserWindow): void {
  executor = new PlaywrightExecutor(win)

  ipcMain.handle('automation:executeStep', async (_event, step: AutomationStep) => {
    if (!executor) throw new Error('Automation executor not initialized')
    return executor.executeStep(step)
  })
}
