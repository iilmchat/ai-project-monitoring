import type { ReactNode } from 'react'

type InlineToken =
  | { type: 'text'; value: string }
  | { type: 'strong'; value: string }
  | { type: 'emphasis'; value: string }
  | { type: 'code'; value: string }
  | { type: 'link'; value: string; href: string }

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'code'; language: string; code: string }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'quote'; text: string }
  | { type: 'table'; header: string[]; rows: string[][] }
  | { type: 'hr' }

interface MarkdownViewProps {
  content: string
  onOpenLink?: (href: string) => void
}

const TABLE_SEPARATOR = /^\s*\|?[\s:|-]+\|?\s*$/

export default function MarkdownView({ content, onOpenLink }: MarkdownViewProps) {
  const blocks = parseBlocks(content)

  return (
    <div className="space-y-3 text-sm leading-6 text-slate-700 dark:text-slate-300">
      {blocks.map((block, index) => renderBlock(block, index, onOpenLink))}
    </div>
  )
}

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    const fence = trimmed.match(/^```([\w.+-]*)\s*$/)
    if (fence) {
      const language = fence[1] ?? ''
      const code: string[] = []
      index += 1
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        code.push(lines[index])
        index += 1
      }
      index += 1
      blocks.push({ type: 'code', language, code: code.join('\n') })
      continue
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] })
      index += 1
      continue
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: 'hr' })
      index += 1
      continue
    }

    if (trimmed.startsWith('>')) {
      const quote: string[] = []
      while (index < lines.length && lines[index].trim().startsWith('>')) {
        quote.push(lines[index].trim().replace(/^>\s?/, ''))
        index += 1
      }
      blocks.push({ type: 'quote', text: quote.join(' ') })
      continue
    }

    if (isTableStart(lines, index)) {
      const header = parseTableRow(lines[index])
      index += 2
      const rows: string[][] = []
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(parseTableRow(lines[index]))
        index += 1
      }
      blocks.push({ type: 'table', header, rows })
      continue
    }

    const unordered = trimmed.match(/^[-*+]\s+(.*)$/)
    const ordered = trimmed.match(/^\d+\.\s+(.*)$/)
    if (unordered || ordered) {
      const orderedList = ordered !== null
      const items: string[] = []
      while (index < lines.length) {
        const candidate = lines[index].trim()
        const match = orderedList
          ? candidate.match(/^\d+\.\s+(.*)$/)
          : candidate.match(/^[-*+]\s+(.*)$/)
        if (!match) {
          break
        }
        items.push(match[1])
        index += 1
      }
      blocks.push({ type: 'list', ordered: orderedList, items })
      continue
    }

    const paragraph: string[] = [trimmed]
    index += 1
    while (index < lines.length) {
      const candidate = lines[index].trim()
      if (
        !candidate ||
        candidate.startsWith('#') ||
        candidate.startsWith('>') ||
        /^[-*+]\s+/.test(candidate) ||
        /^\d+\.\s+/.test(candidate) ||
        candidate.startsWith('```') ||
        isTableStart(lines, index)
      ) {
        break
      }
      paragraph.push(candidate)
      index += 1
    }
    blocks.push({ type: 'paragraph', text: paragraph.join(' ') })
  }

  return blocks
}

function isTableStart(lines: string[], index: number): boolean {
  return (
    lines[index].includes('|') &&
    index + 1 < lines.length &&
    TABLE_SEPARATOR.test(lines[index + 1]) &&
    lines[index + 1].includes('-')
  )
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function renderBlock(
  block: Block,
  key: number,
  onOpenLink?: (href: string) => void,
): ReactNode {
  switch (block.type) {
    case 'heading': {
      const className =
        block.level <= 1
          ? 'text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-100'
          : block.level === 2
            ? 'text-lg font-semibold text-slate-900 dark:text-slate-100'
            : 'text-base font-semibold text-slate-800 dark:text-slate-200'
      const content = renderInline(block.text, onOpenLink)
      if (block.level === 1) {
        return (
          <h1 key={key} className={className}>
            {content}
          </h1>
        )
      }
      if (block.level === 2) {
        return (
          <h2 key={key} className={className}>
            {content}
          </h2>
        )
      }
      return (
        <h3 key={key} className={className}>
          {content}
        </h3>
      )
    }
    case 'paragraph':
      return <p key={key}>{renderInline(block.text, onOpenLink)}</p>
    case 'code':
      return (
        <pre
          key={key}
          className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100 dark:bg-slate-950"
        >
          <code>{block.code}</code>
        </pre>
      )
    case 'list': {
      const items = block.items.map((item, itemIndex) => (
        <li key={itemIndex}>{renderInline(item, onOpenLink)}</li>
      ))
      return block.ordered ? (
        <ol key={key} className="list-decimal space-y-1 pl-5">
          {items}
        </ol>
      ) : (
        <ul key={key} className="list-disc space-y-1 pl-5">
          {items}
        </ul>
      )
    }
    case 'quote':
      return (
        <blockquote
          key={key}
          className="border-l-4 border-slate-300 pl-3 text-slate-500 dark:border-slate-600 dark:text-slate-400"
        >
          {renderInline(block.text, onOpenLink)}
        </blockquote>
      )
    case 'table':
      return (
        <div key={key} className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-xs dark:divide-slate-700">
            <thead className="bg-slate-50 dark:bg-slate-800/60">
              <tr>
                {block.header.map((cell, cellIndex) => (
                  <th key={cellIndex} className="px-2 py-1 text-left font-semibold">
                    {renderInline(cell, onOpenLink)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {block.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-2 py-1 align-top">
                      {renderInline(cell, onOpenLink)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    case 'hr':
      return <hr key={key} className="border-slate-200 dark:border-slate-700" />
  }
}

function tokenizeInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = []
  const pattern = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*/g
  let lastIndex = 0
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0
    if (index > lastIndex) {
      tokens.push({ type: 'text', value: text.slice(lastIndex, index) })
    }
    if (match[1] !== undefined && match[2] !== undefined) {
      tokens.push({ type: 'link', value: match[1], href: match[2] })
    } else if (match[3] !== undefined) {
      tokens.push({ type: 'strong', value: match[3] })
    } else if (match[4] !== undefined) {
      tokens.push({ type: 'code', value: match[4] })
    } else if (match[5] !== undefined) {
      tokens.push({ type: 'emphasis', value: match[5] })
    }
    lastIndex = index + match[0].length
  }
  if (lastIndex < text.length) {
    tokens.push({ type: 'text', value: text.slice(lastIndex) })
  }
  return tokens
}

function renderInline(
  text: string,
  onOpenLink?: (href: string) => void,
): ReactNode[] {
  return tokenizeInline(text).map((token, index) => {
    switch (token.type) {
      case 'strong':
        return <strong key={index}>{token.value}</strong>
      case 'emphasis':
        return <em key={index}>{token.value}</em>
      case 'code':
        return (
          <code
            key={index}
            className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-800 dark:bg-slate-800 dark:text-slate-200"
          >
            {token.value}
          </code>
        )
      case 'link':
        return renderLink(token.value, token.href, index, onOpenLink)
      default:
        return token.value
    }
  })
}

function renderLink(
  label: string,
  href: string,
  key: number,
  onOpenLink?: (href: string) => void,
): ReactNode {
  const external = /^(https?:|mailto:)/i.test(href)
  if (external) {
    return (
      <a
        key={key}
        href={href}
        target="_blank"
        rel="noreferrer"
        className="font-medium text-primary hover:underline"
      >
        {label}
      </a>
    )
  }
  if (href.startsWith('#')) {
    return (
      <a key={key} href={href} className="font-medium text-primary hover:underline">
        {label}
      </a>
    )
  }
  return (
    <button
      key={key}
      type="button"
      onClick={() => onOpenLink?.(href)}
      className="text-left font-medium text-primary hover:underline"
    >
      {label}
    </button>
  )
}
