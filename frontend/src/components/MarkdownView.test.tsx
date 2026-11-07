import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { resolveDocumentPath } from '../utils/markdownLinks'
import MarkdownView from './MarkdownView'

describe('MarkdownView', () => {
  it('renders headings, code and internal links', async () => {
    const onOpenLink = vi.fn()
    render(
      <MarkdownView
        content={'# Project\n\nSee [SPEC](docs/SPEC.md) and `npm test`.\n'}
        onOpenLink={onOpenLink}
      />,
    )

    expect(screen.getByRole('heading', { level: 1, name: 'Project' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'SPEC' }))
    expect(onOpenLink).toHaveBeenCalledWith('docs/SPEC.md')
  })

  it('does not render raw HTML', () => {
    render(<MarkdownView content={'<script>alert(1)</script>'} />)

    expect(screen.queryByText('alert(1)')).not.toBeInTheDocument()
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument()
  })
})

describe('resolveDocumentPath', () => {
  it('resolves relative links from the current document', () => {
    expect(resolveDocumentPath('README.md', 'docs/SPEC.md')).toBe('docs/SPEC.md')
    expect(resolveDocumentPath('docs/ARCHITECTURE.md', '../SPEC.md')).toBe('SPEC.md')
    expect(resolveDocumentPath('docs/ARCHITECTURE.md', './adr/0003-read-only-policy.md')).toBe(
      'docs/adr/0003-read-only-policy.md',
    )
  })

  it('rejects external links, images and traversal', () => {
    expect(resolveDocumentPath('README.md', 'https://example.com/README.md')).toBeNull()
    expect(resolveDocumentPath('README.md', 'logo.png')).toBeNull()
    expect(resolveDocumentPath('README.md', '../../etc/passwd.md')).toBeNull()
  })
})
