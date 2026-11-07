const DOCUMENT_SUFFIXES = ['.md', '.markdown', '.txt']

/**
 * Resolve a Markdown link relative to the currently open document.
 * Returns ``null`` for external links, images and paths escaping the repo.
 */
export function resolveDocumentPath(currentPath: string, href: string): string | null {
  const withoutFragment = href.split('#')[0].split('?')[0]
  if (!withoutFragment || /^(https?:|mailto:)/i.test(withoutFragment)) {
    return null
  }
  if (!DOCUMENT_SUFFIXES.some((suffix) => withoutFragment.toLowerCase().endsWith(suffix))) {
    return null
  }
  const decoded = decodeURIComponent(withoutFragment).replaceAll('\\', '/')
  const base = currentPath.includes('/')
    ? currentPath.slice(0, currentPath.lastIndexOf('/'))
    : ''
  const combined = decoded.startsWith('/') ? decoded.slice(1) : `${base}/${decoded}`
  const parts: string[] = []
  for (const segment of combined.split('/')) {
    if (!segment || segment === '.') {
      continue
    }
    if (segment === '..') {
      if (parts.length === 0) {
        return null
      }
      parts.pop()
      continue
    }
    parts.push(segment)
  }
  return parts.join('/')
}
