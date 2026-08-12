import { StudioElement } from '../types/studio'

const STUDIO_SCHEMA: StudioElement[] = [
  // TopBar
  {
    id: 'topbar-canvas',
    screen: 'TopBar',
    type: 'button',
    label: 'Canvas',
    description: 'Switch to the Canvas (flow editor) view.',
  },
  {
    id: 'topbar-plan',
    screen: 'TopBar',
    type: 'button',
    label: 'Plan',
    description: 'Switch to the Plan view.',
  },
  {
    id: 'topbar-monitor',
    screen: 'TopBar',
    type: 'button',
    label: 'Monitor',
    description: 'Switch to the Monitor view to observe running flows.',
  },
  {
    id: 'topbar-publish',
    screen: 'TopBar',
    type: 'button',
    label: 'Publish',
    description: 'Publish the current flow.',
  },
  {
    id: 'topbar-back',
    screen: 'TopBar',
    type: 'button',
    label: 'Back to projects',
    description: 'Navigate back to the projects list.',
  },
  {
    id: 'topbar-toggle-conductor',
    screen: 'TopBar',
    type: 'button',
    label: 'Toggle Conductor',
    description: 'Show or hide the Conductor AI chat panel.',
  },
  {
    id: 'topbar-push-hooks',
    screen: 'TopBar',
    type: 'button',
    label: 'Push hooks to server',
    description: 'Push the current flow hooks to the server.',
  },
  {
    id: 'topbar-shell',
    screen: 'TopBar',
    type: 'button',
    label: '+ Shell',
    description: 'Open a new shell terminal tab.',
  },
  {
    id: 'topbar-claude-code',
    screen: 'TopBar',
    type: 'button',
    label: 'Claude Code',
    description: 'Open a Claude Code terminal session.',
  },
  {
    id: 'topbar-codex',
    screen: 'TopBar',
    type: 'button',
    label: 'Codex',
    description: 'Open a Codex terminal session.',
  },
  {
    id: 'topbar-antigravity',
    screen: 'TopBar',
    type: 'button',
    label: 'Antigravity',
    description: 'Open an Antigravity (agy) terminal session.',
  },
  // Sidebar
  {
    id: 'sidebar-workspace-tab',
    screen: 'Sidebar',
    type: 'button',
    label: 'WORKSPACE',
    description: 'Switch the sidebar to the Workspace tab.',
  },
  {
    id: 'sidebar-library-tab',
    screen: 'Sidebar',
    type: 'button',
    label: 'LIBRARY',
    description: 'Switch the sidebar to the Library tab.',
  },
  {
    id: 'sidebar-search-library',
    screen: 'Sidebar',
    type: 'input',
    label: 'Search library…',
    description: 'Search the component library.',
  },
  {
    id: 'sidebar-filter',
    screen: 'Sidebar',
    type: 'input',
    label: 'Filter…',
    description: 'Filter items in the sidebar.',
  },
  {
    id: 'sidebar-resize',
    screen: 'Sidebar',
    type: 'panel',
    label: 'Resize sidebar',
    description: 'Drag the sidebar edge to resize its width.',
  },
  // FlowEditor toolbar
  {
    id: 'floweditor-save',
    screen: 'FlowEditor',
    type: 'button',
    label: 'Save',
    description: 'Save the current flow.',
  },
  {
    id: 'floweditor-add-state',
    screen: 'FlowEditor',
    type: 'button',
    label: '+ Add state',
    description: 'Add a new state node to the flow canvas.',
  },
  {
    id: 'floweditor-auto-layout',
    screen: 'FlowEditor',
    type: 'button',
    label: 'Auto-layout',
    description: 'Automatically arrange all nodes on the canvas.',
  },
  {
    id: 'floweditor-zoom-fit',
    screen: 'FlowEditor',
    type: 'button',
    label: 'Fit to screen',
    description: 'Zoom the canvas to fit all nodes in view.',
  },
  {
    id: 'floweditor-visual',
    screen: 'FlowEditor',
    type: 'button',
    label: 'Visual',
    description: 'Switch the flow editor to the Visual (canvas) mode.',
  },
  {
    id: 'floweditor-yaml',
    screen: 'FlowEditor',
    type: 'button',
    label: 'YAML',
    description: 'Switch the flow editor to the YAML text mode.',
  },
  // FlowEditor node panel
  {
    id: 'floweditor-state-id',
    screen: 'FlowEditor',
    type: 'input',
    label: 'State ID',
    description: 'The identifier for the selected flow state node.',
  },
  {
    id: 'floweditor-remove-from-canvas',
    screen: 'FlowEditor',
    type: 'button',
    label: 'Remove from canvas',
    description: 'Remove the selected state node from the canvas.',
  },
  {
    id: 'floweditor-assigned-behavior',
    screen: 'FlowEditor',
    type: 'select',
    label: 'Assigned behavior',
    description: 'The behavior (skill) assigned to this state node.',
  },
  // FlowEditor edge panel
  {
    id: 'floweditor-delete-connection',
    screen: 'FlowEditor',
    type: 'button',
    label: 'Delete connection',
    description: 'Delete the selected edge (transition) between states.',
  },
  // FlowEditor modals
  {
    id: 'modal-cancel',
    screen: 'Modal',
    type: 'button',
    label: 'Cancel',
    description: 'Dismiss the current modal dialog without saving.',
  },
  {
    id: 'modal-discard-changes',
    screen: 'Modal',
    type: 'button',
    label: 'Discard changes',
    description: 'Discard unsaved changes and close the modal.',
  },
  // Panel
  {
    id: 'panel-close',
    screen: 'Panel',
    type: 'button',
    label: 'Close panel',
    description: 'Close the currently open side panel.',
  },
  // BottomNav
  {
    id: 'bottomnav-monitor',
    screen: 'BottomNav',
    type: 'button',
    label: 'Monitor',
    description: 'Open the Monitor tab in the bottom navigation.',
  },
  {
    id: 'bottomnav-settings',
    screen: 'BottomNav',
    type: 'button',
    label: 'Settings',
    description: 'Open the Settings tab in the bottom navigation.',
  },
  // ChatPanel
  {
    id: 'chatpanel-message-input',
    screen: 'ChatPanel',
    type: 'input',
    label: 'Message input',
    description: 'The text input area for composing a message to the Conductor.',
  },
  {
    id: 'chatpanel-send',
    screen: 'ChatPanel',
    type: 'button',
    label: 'Send',
    description: 'Send the composed message to the Conductor.',
  },
]

export function getStudioSchema(): StudioElement[] {
  return STUDIO_SCHEMA
}

function getSchemaForScreen(screen: string): StudioElement[] {
  return STUDIO_SCHEMA.filter((el) => el.screen === screen)
}
