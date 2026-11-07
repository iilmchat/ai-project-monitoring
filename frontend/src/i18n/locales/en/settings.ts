export const settings = {
  'settings.title': 'Settings',
  'settings.subtitle': 'Values are stored in the database and applied without a restart.',
  'settings.loadError': 'Could not load settings.',
  'settings.saveError': 'Could not save settings.',
  'settings.saved': 'Settings saved.',
  'settings.scanRoots': 'SCAN_ROOTS (comma-separated paths)',
  'settings.canonicalProvider': 'Default canonical provider',
  'settings.aiSection': 'AI / LLM',
  'settings.enableAi': 'Enable AI features',
  'settings.endpoint': 'LLM endpoint (OpenAI-compatible)',
  'settings.model': 'Model',
  'settings.apiKey': 'API key (optional)',
  'settings.timeout': 'Timeout, s',
  'settings.maxDiff': 'Max diff, characters',
  'settings.allowRemote': 'Allow remote endpoint (code will be sent off this machine)',
  'settings.tokenHint':
    'An empty token field means “keep current”. The mask shows the stored value.',
  'settings.workspace': 'Workspace',
  'settings.workspaceHint':
    'Export and import UI settings: Saved Views, visible columns and widths. Tokens and scan paths are never exported.',
  'settings.exportWorkspace': 'Export settings (JSON)',
  'settings.importWorkspace': 'Import settings',
  'settings.workspaceFormat': 'Format: {filename} · schema version 1 · up to 1 MiB.',
  'settings.workspaceExported': 'Workspace exported: {filename}',
  'settings.workspaceImported': 'Workspace settings imported.',
  'settings.workspaceImportError':
    'Could not import settings: invalid file format or version.',
} as const
