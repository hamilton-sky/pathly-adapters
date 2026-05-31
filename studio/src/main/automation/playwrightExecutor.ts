import { BrowserWindow } from 'electron'

export type StepType = 'click' | 'fill' | 'select' | 'navigate'

export interface AutomationStep {
  type: StepType
  label: string
  value?: string
}

export interface StepResult {
  success: boolean
  tier: 1 | 2 | 3
  error?: string
  resolvedSelector?: string
}

export class PlaywrightExecutor {
  constructor(private win: BrowserWindow) {}

  async executeStep(step: AutomationStep): Promise<StepResult> {
    const tier1Selector = await this.tier1(step)
    if (tier1Selector) {
      await this.performAction(tier1Selector, step)
      return { success: true, tier: 1, resolvedSelector: tier1Selector }
    }

    const tier2Selector = await this.tier2(step)
    if (tier2Selector) {
      await this.performAction(tier2Selector, step)
      return { success: true, tier: 2, resolvedSelector: tier2Selector }
    }

    const tier3Selector = await this.evalInPage<string | null>(
      `window.__pathlyResolveElement(${JSON.stringify(step.label)})`
    )
    if (tier3Selector) {
      await this.performAction(tier3Selector, step)
      return { success: true, tier: 3, resolvedSelector: tier3Selector }
    }

    return { success: false, tier: 3, error: 'Element not found: ' + step.label }
  }

  private async evalInPage<T>(script: string): Promise<T> {
    return this.win.webContents.executeJavaScript(script)
  }

  private async tier1(step: AutomationStep): Promise<string | null> {
    return this.evalInPage<string | null>(`
      (() => {
        const label = ${JSON.stringify(step.label)};
        let el = document.querySelector('[data-label="' + label + '"]');
        if (el) return '[data-label="' + label + '"]';
        el = document.querySelector('[aria-label="' + label + '"]');
        if (el) return '[aria-label="' + label + '"]';
        el = document.querySelector('[placeholder="' + label + '"]');
        if (el) return '[placeholder="' + label + '"]';
        const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
        const btn = buttons.find(b => b.textContent?.trim() === label);
        if (btn) {
          if (btn.id) return '#' + btn.id;
          if (btn.getAttribute('data-label')) return '[data-label="' + btn.getAttribute('data-label') + '"]';
        }
        return null;
      })()
    `)
  }

  private async tier2(step: AutomationStep): Promise<string | null> {
    return this.evalInPage<string | null>(`
      (() => {
        const label = ${JSON.stringify(step.label.toLowerCase())};
        const roles = ['button', 'textbox', 'combobox', 'link', 'menuitem', 'option'];
        for (const role of roles) {
          let query;
          if (role === 'button') query = '[role="button"], button';
          else if (role === 'textbox') query = 'input, textarea';
          else if (role === 'combobox') query = 'select';
          else if (role === 'link') query = 'a';
          else query = '[role="' + role + '"]';
          const els = Array.from(document.querySelectorAll(query));
          const match = els.find(el => {
            const text = (el.textContent || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').toLowerCase();
            return text.includes(label);
          });
          if (match) {
            if (match.id) return '#' + match.id;
            if (match.className) return '.' + Array.from(match.classList).join('.');
            return null;
          }
        }
        return null;
      })()
    `)
  }

  private async performAction(selector: string, step: AutomationStep): Promise<void> {
    const escaped = JSON.stringify(selector)
    const value = JSON.stringify(step.value ?? '')
    switch (step.type) {
      case 'click':
        await this.evalInPage(`document.querySelector(${escaped})?.click()`)
        break
      case 'fill':
        await this.evalInPage(`
          (() => {
            const el = document.querySelector(${escaped});
            if (el) {
              el.focus();
              const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
              const setter = desc?.set;
              if (setter) {
                setter.call(el, ${value});
              } else {
                el.value = ${value};
              }
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
            }
          })()
        `)
        break
      case 'select':
        await this.evalInPage(`
          (() => {
            const el = document.querySelector(${escaped});
            if (el) { el.value = ${value}; el.dispatchEvent(new Event('change', {bubbles:true})); }
          })()
        `)
        break
      case 'navigate':
        await this.evalInPage(`window.__pathlyNavigate(${JSON.stringify(step.label)})`)
        break
    }
  }
}
