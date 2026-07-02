import type { TreeNode } from '../types'

/** Default demo workspace — a real project tree with a `pathly/plans` dir. */
export const SAMPLE_TREE: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      {
        name: 'routes',
        type: 'folder',
        children: [
          { name: 'auth.ts', type: 'file' },
          { name: 'users.ts', type: 'file' },
        ],
      },
      { name: 'db', type: 'folder', children: [{ name: 'client.ts', type: 'file' }] },
      { name: 'index.ts', type: 'file' },
      { name: 'server.ts', type: 'file' },
    ],
  },
  {
    name: 'pathly',
    type: 'folder',
    children: [
      {
        name: 'plans',
        type: 'folder',
        children: [
          {
            name: 'auth-refactor',
            type: 'folder',
            state: 'BUILDING',
            children: [
              { name: 'STATE.json', type: 'file' },
              { name: 'plan.md', type: 'file' },
            ],
          },
          {
            name: 'search-index',
            type: 'folder',
            state: 'DONE',
            children: [{ name: 'STATE.json', type: 'file' }],
          },
        ],
      },
    ],
  },
  { name: 'tests', type: 'folder', children: [{ name: 'auth.test.ts', type: 'file' }] },
  { name: 'package.json', type: 'file' },
  { name: 'tsconfig.json', type: 'file' },
  { name: 'README.md', type: 'file' },
]

export const SAMPLE_COLLAPSED: Record<string, boolean> = {
  'pathly/plans/auth-refactor': false,
  'pathly/plans/search-index': false,
  'src/db': false,
}
