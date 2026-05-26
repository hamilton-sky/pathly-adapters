export interface StudioElement {
  id: string
  screen: string
  type: 'button' | 'input' | 'select' | 'panel'
  label: string
  description: string
}
