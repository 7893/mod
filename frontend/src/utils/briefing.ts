export interface BriefingSection {
  title: string
  items: string[]
}

const GENERIC_TITLES = new Set(['智能研判报告', '每日指挥部决策简报', '每日简报'])

function cleanInlineMarkdown(value: string): string {
  return value
    .replace(/^\*\*(.+)\*\*$/, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .trim()
}

function headingText(line: string): string | null {
  const markdownHeading = line.match(/^#{1,6}\s+(.+)$/)
  if (markdownHeading) return cleanInlineMarkdown(markdownHeading[1]).replace(/[:：]$/, '')

  const boldHeading = line.match(/^\*\*(.+)\*\*[:：]?$/)
  return boldHeading ? cleanInlineMarkdown(boldHeading[1]).replace(/[:：]$/, '') : null
}

export function parseBriefingSections(content?: string | null): BriefingSection[] {
  if (!content?.trim()) return []

  const sections: BriefingSection[] = []
  let current: BriefingSection | null = null

  const ensureSection = () => {
    if (!current) {
      current = { title: '简报摘要', items: [] }
      sections.push(current)
    }
    return current
  }

  for (const rawLine of content.replace(/\r\n?/g, '\n').split('\n')) {
    const line = rawLine.trim()
    if (!line) continue

    const heading = headingText(line)
    if (heading) {
      if (GENERIC_TITLES.has(heading)) continue
      current = { title: heading, items: [] }
      sections.push(current)
      continue
    }

    const listItem = line.match(/^(?:[-*•]|\d+[.)])\s+(.+)$/)
    ensureSection().items.push(cleanInlineMarkdown(listItem?.[1] ?? line))
  }

  return sections.filter((section) => section.items.length > 0)
}
