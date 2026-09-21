/**
 * "Markdown simple" for descriptions and comments (SPEC §7).
 *
 * Safety: raw HTML is disabled, so whatever a user types is escaped by
 * markdown-it; its link validator refuses javascript: and similar schemes.
 * The output is therefore safe to inject with v-html, and only through
 * <MarkdownView>. Never v-html anything that did not go through render().
 */
import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: false, linkify: true, breaks: true })

// Links open in a new tab and never hand over window.opener.
const defaultLinkOpen =
  markdown.renderer.rules.link_open ??
  ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet('target', '_blank')
  tokens[index].attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLinkOpen(tokens, index, options, env, self)
}

// Same pattern as the backend (apps/tasks/services.py::MENTION).
const MENTION = /(^|[^\w@.])@([A-Za-z0-9_.-]{3,30})/g

/**
 * Wraps "@username" in <span class="mention">. Done on the TOKEN stream, on
 * plain text outside links only: working on the rendered HTML string would
 * corrupt an URL such as https://site.ch/@helder.
 */
markdown.core.ruler.push('mentions', (state) => {
  for (const block of state.tokens) {
    if (block.type !== 'inline' || !block.children) continue
    const children: typeof block.children = []
    let insideLink = 0
    for (const token of block.children) {
      if (token.type === 'link_open') insideLink += 1
      if (token.type === 'link_close') insideLink -= 1
      if (token.type !== 'text' || insideLink > 0 || !token.content.includes('@')) {
        children.push(token)
        continue
      }
      let cursor = 0
      const pushText = (content: string) => {
        if (!content) return
        const text = new state.Token('text', '', 0)
        text.content = content
        children.push(text)
      }
      for (const match of token.content.matchAll(MENTION)) {
        const start = match.index + match[1].length
        pushText(token.content.slice(cursor, start))
        const open = new state.Token('mention_open', 'span', 1)
        open.attrSet('class', 'mention')
        children.push(open)
        pushText(`@${match[2]}`)
        children.push(new state.Token('mention_close', 'span', -1))
        cursor = start + 1 + match[2].length
      }
      pushText(token.content.slice(cursor))
    }
    block.children = children
  }
})

export function render(source: string): string {
  return markdown.render(source ?? '')
}
