import { describe, expect, it } from 'vitest'

import { render } from './markdown'

describe('render (markdown)', () => {
  it('renders basic markdown', () => {
    expect(render('**gras** et *italique*')).toContain('<strong>gras</strong>')
    expect(render('- un\n- deux')).toContain('<li>un</li>')
  })

  it('escapes raw HTML instead of executing it', () => {
    const html = render('<img src=x onerror=alert(1)> <script>alert(1)</script>')

    expect(html).not.toContain('<img')
    expect(html).not.toContain('<script')
    expect(html).toContain('&lt;script&gt;')
  })

  it('refuses javascript: links', () => {
    expect(render('[clic](javascript:alert(1))')).not.toContain('href')
  })

  it('opens links in a new tab without window.opener', () => {
    const html = render('https://100sations.ch')

    expect(html).toContain('target="_blank"')
    expect(html).toContain('noopener')
  })

  it('highlights mentions', () => {
    expect(render('Salut @helder, ok ?')).toContain('<span class="mention">@helder</span>')
    expect(render('(@helder)')).toContain('<span class="mention">@helder</span>')
  })

  it('leaves e-mail addresses and URLs alone', () => {
    expect(render('mail helder@exemple.ch')).not.toContain('mention')
    const html = render('https://site.ch/@helder')
    expect(html).not.toContain('mention')
    expect(html).toContain('href="https://site.ch/@helder"')
  })
})
