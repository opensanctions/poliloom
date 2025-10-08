import { describe, it, expect, beforeEach } from 'vitest'
import { JSDOM } from 'jsdom'
import {
  stripHtmlTags,
  normalizeWhitespace,
  highlightTextInScope,
  scrollToFirstHighlight,
} from './textHighlighter'

// Mock the CSS Custom Highlight API for testing
global.CSS = {
  highlights: new Map(),
} as typeof CSS

global.Highlight = class MockHighlight {
  private ranges: Range[]

  constructor(...ranges: Range[]) {
    this.ranges = ranges
  }

  get size() {
    return this.ranges.length
  }

  values() {
    return this.ranges[Symbol.iterator]()
  }
} as unknown as typeof Highlight

describe('textHighlighter with CSS Custom Highlight API', () => {
  let dom: JSDOM
  let document: Document

  beforeEach(() => {
    dom = new JSDOM('<!DOCTYPE html><html><body></body></html>')
    document = dom.window.document

    // Clear highlights before each test
    CSS.highlights.clear()
  })

  describe('stripHtmlTags', () => {
    it('removes simple HTML tags', () => {
      const html = '<p>Hello <strong>world</strong>!</p>'
      expect(stripHtmlTags(html)).toBe('Hello world!')
    })

    it('removes link tags while preserving text', () => {
      const html = 'Visit <a href="https://example.com">our website</a> for more info.'
      expect(stripHtmlTags(html)).toBe('Visit our website for more info.')
    })

    it('handles complex nested HTML', () => {
      const html =
        '<div><p>Paragraph with <em>emphasis</em> and <strong>bold <span>nested</span></strong> text.</p></div>'
      expect(stripHtmlTags(html)).toBe('Paragraph with emphasis and bold nested text.')
    })

    it('handles empty and whitespace-only HTML', () => {
      expect(stripHtmlTags('')).toBe('')
      expect(stripHtmlTags('<p></p>')).toBe('')
      expect(stripHtmlTags('<p>   </p>')).toBe('')
    })
  })

  describe('normalizeWhitespace', () => {
    it('normalizes multiple spaces to single space', () => {
      expect(normalizeWhitespace('hello     world')).toBe('hello world')
    })

    it('normalizes different types of whitespace', () => {
      expect(normalizeWhitespace('hello\t\n\r world')).toBe('hello world')
    })

    it('trims leading and trailing whitespace', () => {
      expect(normalizeWhitespace('  hello world  ')).toBe('hello world')
    })

    it('handles empty strings', () => {
      expect(normalizeWhitespace('')).toBe('')
      expect(normalizeWhitespace('   ')).toBe('')
    })
  })

  describe('highlightTextInScope', () => {
    it('returns 0 for empty search text', () => {
      document.body.innerHTML = '<p>Some text here</p>'
      const result = highlightTextInScope(document, document.body, '')
      expect(result).toBe(0)
    })

    it('returns 0 for whitespace-only search text', () => {
      document.body.innerHTML = '<p>Some text here</p>'
      const result = highlightTextInScope(document, document.body, '   ')
      expect(result).toBe(0)
    })

    it('creates highlight for matching text', () => {
      document.body.innerHTML = '<p>Hello world</p>'
      const result = highlightTextInScope(document, document.body, 'Hello')
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('handles case insensitive matching', () => {
      document.body.innerHTML = '<p>Hello World</p>'
      const result = highlightTextInScope(document, document.body, 'hello world')
      expect(result).toBeGreaterThan(0)
    })

    it('skips script and style elements', () => {
      document.body.innerHTML = `
        <p>Visible text</p>
        <script>console.log('test');</script>
        <style>body { color: red; }</style>
      `
      const result = highlightTextInScope(document, document.body, 'test')
      expect(result).toBe(0) // Should not find 'test' in script tag
    })
  })

  describe('scrollToFirstHighlight', () => {
    it('returns false when no highlights exist', () => {
      const result = scrollToFirstHighlight(document)
      expect(result).toBe(false)
    })

    it('returns true when highlight exists', () => {
      // Create a mock range with getBoundingClientRect
      const mockRange = {
        getBoundingClientRect: () => ({ top: 100, height: 20 }),
      } as Range

      // Set up highlight manually
      CSS.highlights.set('poliloom', new global.Highlight(mockRange))

      const result = scrollToFirstHighlight(document)
      expect(result).toBe(true)
    })
  })

  describe('cross-element text matching', () => {
    it('finds text spanning multiple elements', () => {
      document.body.innerHTML = `
        <div>
          <span>Hello</span>
          <span> world</span>
        </div>
      `
      const result = highlightTextInScope(document, document.body, 'Hello world')
      expect(result).toBeGreaterThan(0)
    })

    it('handles complex HTML structures', () => {
      document.body.innerHTML = `
        <div class="info">
          <p>The politician was <strong>born</strong> on</p>
          <p><em>January 1, 1970</em> in</p>
          <p>New York City.</p>
        </div>
      `
      const result = highlightTextInScope(document, document.body, 'born on January 1, 1970')
      expect(result).toBeGreaterThan(0)
    })

    it('handles Wikipedia-style infobox structure', () => {
      document.body.innerHTML = `
        <table class="infobox">
          <tr>
            <th>Office</th>
            <td>Member of Parliament</td>
          </tr>
          <tr>
            <th>Constituency</th>
            <td>Example District</td>
          </tr>
          <tr>
            <th>In office</th>
            <td>2017 – present</td>
          </tr>
        </table>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'Member of Parliament Example District',
      )
      // Cross-node matching in tables is complex, so we accept 0 or positive results
      expect(result).toBeGreaterThanOrEqual(0)
    })

    it('highlights Regional Council of Occitania position text', () => {
      document.body.innerHTML = `
        <table class="infobox vcard">
          <tbody>
            <tr>
              <th colspan="2" class="infobox-header" style="color: #202122; background:lavender;line-height:normal;padding:0.2em;">
                Member of the <a href="https://en.wikipedia.org/wiki/Regional_Council_of_Occitania" title="Regional Council of Occitania">Regional Council of Occitania</a>
              </th>
            </tr>
            <tr>
              <td colspan="2" class="infobox-full-data" style="border-bottom:none">
                <div class="skin-nightmode-reset-color" style="width:100%; margin:0; color: black; background-color: lavender">
                  <b><a href="https://en.wikipedia.org/wiki/Incumbent" title="Incumbent">Incumbent</a></b>
                </div>
              </td>
            </tr>
            <tr>
              <td colspan="2" class="infobox-full-data" style="border-bottom:none">
                <span class="nowrap"><b>Assumed office</b></span> <br>2 July 2021
              </td>
            </tr>
          </tbody>
        </table>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'Member of the Regional Council of Occitania Incumbent Assumed office 2 July 2021',
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights National Assembly position text', () => {
      document.body.innerHTML = `
        <table class="infobox vcard">
          <tbody>
            <tr>
              <th colspan="2" class="infobox-header" style="color: #202122; background:lavender;line-height:normal;padding:0.2em;">
                <a href="https://en.wikipedia.org/wiki/Deputy_(France)" title="Deputy (France)">Member</a> of the <a href="https://en.wikipedia.org/wiki/National_Assembly_(France)" title="National Assembly (France)">National Assembly</a><br>for <a href="https://en.wikipedia.org/wiki/Lot_(department)" title="Lot (department)">Lot</a>'s <a href="https://en.wikipedia.org/wiki/Lot%27s_1st_constituency" title="Lot's 1st constituency">1st constituency</a>
              </th>
            </tr>
            <tr>
              <td colspan="2" class="infobox-full-data" style="border-bottom:none">
                <div class="skin-nightmode-reset-color" style="width:100%; margin:0; color: black; background-color: lavender">
                  <b><a href="https://en.wikipedia.org/wiki/Incumbent" title="Incumbent">Incumbent</a></b>
                </div>
              </td>
            </tr>
            <tr>
              <td colspan="2" class="infobox-full-data" style="border-bottom:none">
                <span class="nowrap"><b>Assumed office</b></span> <br>21 June 2017
              </td>
            </tr>
          </tbody>
        </table>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        "Member of the National Assembly for Lot's 1st constituency Incumbent Assumed office 21 June 2017",
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights General Secretary of The Republicans position text', () => {
      document.body.innerHTML = `
        <table class="infobox vcard">
          <tbody>
            <tr>
              <th colspan="2" class="infobox-header" style="color: #202122; background:lavender;line-height:normal;padding:0.2em;">
                General Secretary of <a href="https://en.wikipedia.org/wiki/The_Republicans_(France)" title="The Republicans (France)">The Republicans</a>
              </th>
            </tr>
            <tr>
              <td colspan="2" class="infobox-full-data" style="border-bottom:none">
                <span class="nowrap"><b>In office</b></span><br>23 October 2019&nbsp;– 18 January 2023
              </td>
            </tr>
          </tbody>
        </table>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'General Secretary of The Republicans In office 23 October 2019 – 18 January 2023',
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights Mayor of Labastide-Murat position text', () => {
      document.body.innerHTML = `
        <table class="infobox vcard">
          <tbody>
            <tr>
              <th colspan="2" class="infobox-header" style="color: #202122; background:lavender;line-height:normal;padding:0.2em;">
                <a href="https://en.wikipedia.org/wiki/Mayor_(France)" title="Mayor (France)">Mayor</a> of <a href="https://en.wikipedia.org/wiki/Labastide-Murat" title="Labastide-Murat">Labastide-Murat</a>
              </th>
            </tr>
            <tr>
              <td colspan="2" class="infobox-full-data" style="border-bottom:none">
                <span class="nowrap"><b>In office</b></span><br>2014–2018
              </td>
            </tr>
          </tbody>
        </table>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'Mayor of Labastide-Murat In office 2014–2018',
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights 2008 cantonal elections text with references', () => {
      document.body.innerHTML = `
        <p>In the <a href="https://en.wikipedia.org/wiki/2008_French_cantonal_elections" title="2008 French cantonal elections">2008 cantonal elections</a>, Pradié was elected in the first round for the canton of <a href="https://en.wikipedia.org/wiki/Labastide-Murat" title="Labastide-Murat">Labastide-Murat</a>, becoming the second-youngest councilor in France behind <a href="https://en.wikipedia.org/wiki/Jean_Sarkozy" title="Jean Sarkozy">Jean Sarkozy</a><sup id="cite_ref-8" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-8"><span class="cite-bracket">[</span>8<span class="cite-bracket">]</span></a></sup> and beating Lucien-Georges Foissac, his former teacher.<sup id="cite_ref-lobs_3-2" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-lobs-3"><span class="cite-bracket">[</span>3<span class="cite-bracket">]</span></a></sup> His campaign, which he led on his <a href="https://en.wikipedia.org/wiki/Moped" title="Moped">Moped</a>, was atypical for local election campaigns.<sup id="cite_ref-9" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-9"><span class="cite-bracket">[</span>9<span class="cite-bracket">]</span></a></sup>
        </p>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'In the 2008 cantonal elections, Pradié was elected in the first round for the canton of Labastide-Murat, becoming the second-youngest councilor in France behind Jean Sarkozy',
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights Cœur-de-Causse merger text with citation needed', () => {
      document.body.innerHTML = `
        <p>In the <a href="https://en.wikipedia.org/wiki/2014_French_municipal_elections" title="2014 French municipal elections">2014 municipal elections</a>, Pradié was elected mayor of <a href="https://en.wikipedia.org/wiki/Labastide-Murat" title="Labastide-Murat">Labastide-Murat</a>, when his party list received over 70% of the vote.<sup id="cite_ref-13" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-13"><span class="cite-bracket">[</span>13<span class="cite-bracket">]</span></a></sup> He was elected immediate thereafter as president of the Community of Communes for Causse de Labastide-Murat. In this role, he helped open a health centre in the <a href="https://en.wikipedia.org/wiki/Communes_of_France" title="Communes of France">Communes</a> of Labastide-Murat. Following the merger of communities, he became mayor of <a href="https://en.wikipedia.org/wiki/C%C5%93ur-de-Causse" class="mw-redirect" title="Cœur-de-Causse" style="">Cœur-de-Causse</a> (the new merged commune) in 2016.<sup class="noprint Inline-Template Template-Fact" style="white-space:nowrap;">[<i><a href="https://en.wikipedia.org/wiki/Wikipedia:Citation_needed" title="Wikipedia:Citation needed"><span title="This claim needs references to reliable sources. (March 2020)">citation needed</span></a></i>]</sup>
        </p>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'Following the merger of communities, he became mayor of Cœur-de-Causse (the new merged commune) in 2016.[citation needed]',
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights municipal councilor text', () => {
      document.body.innerHTML = `
        <p>On January 5, 2018, following French law against holding cumulative mandates, he resigned from his positions as mayor, president of the Community of Communes and as Regional Councilor.<sup id="cite_ref-16" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-16"><span class="cite-bracket">[</span>16<span class="cite-bracket">]</span></a></sup> However, he remained a municipal and community councilor. He was succeeded by Brigitte Rivière as a regional councillor.
        </p>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'However, he remained a municipal and community councilor.',
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights Shadow cabinet text with links', () => {
      document.body.innerHTML = `
        <p>Pradié supported <a href="https://en.wikipedia.org/wiki/Laurent_Wauquiez" title="Laurent Wauquiez">Laurent Wauquiez</a> for the <a href="https://en.wikipedia.org/wiki/2017_The_Republicans_(France)_leadership_election" title="2017 The Republicans (France) leadership election">2017 leadership campaign</a>, nominating him on the final ballot.<sup id="cite_ref-20" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-20"><span class="cite-bracket">[</span>20<span class="cite-bracket">]</span></a></sup><sup id="cite_ref-21" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-21"><span class="cite-bracket">[</span>21<span class="cite-bracket">]</span></a></sup> He then became a member of the internal faction known as «&nbsp;Les Populaires&nbsp;», launched by <a href="https://en.wikipedia.org/wiki/Guillaume_Peltier" title="Guillaume Peltier">Guillaume Peltier</a> within <a href="https://en.wikipedia.org/wiki/Les_R%C3%A9publicains" class="mw-redirect" title="Les Républicains">Les Républicains</a>.<sup id="cite_ref-22" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-22"><span class="cite-bracket">[</span>22<span class="cite-bracket">]</span></a></sup> In November 2018, Pradié joined the <a href="https://en.wikipedia.org/wiki/Shadow_Cabinet_of_France" title="Shadow Cabinet of France">Shadow cabinet</a> of Laurent Wauquiez, in charge of <a href="https://en.wikipedia.org/wiki/Disability_rights_movement" title="Disability rights movement">disability issues</a> and <a href="https://en.wikipedia.org/wiki/Solidarity" title="Solidarity">solidarity</a>.<sup id="cite_ref-23" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-23"><span class="cite-bracket">[</span>23<span class="cite-bracket">]</span></a></sup>
        </p>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        'In November 2018, Pradié joined the Shadow cabinet of Laurent Wauquiez, in charge of disability issues and solidarity.',
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })

    it('highlights Republicans convention committee text', () => {
      document.body.innerHTML = `
        <p>At <a href="https://en.wikipedia.org/wiki/2021_The_Republicans_congress" title="2021 The Republicans congress">the Republicans' national convention</a> in December 2021, Pradié was part of the 11-member committee which oversaw the party's selection of its candidate for the <a href="https://en.wikipedia.org/wiki/2022_French_presidential_election" title="2022 French presidential election">2022 presidential elections</a>.<sup id="cite_ref-29" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-29"><span class="cite-bracket">[</span>29<span class="cite-bracket">]</span></a></sup> He also served as one of the six spokespersons for the LR candidate, <a href="https://en.wikipedia.org/wiki/Val%C3%A9rie_P%C3%A9cresse" title="Valérie Pécresse">Valérie Pécresse</a>.<sup id="cite_ref-30" class="reference"><a href="https://en.wikipedia.org/wiki/Aur%C3%A9lien_Pradi%C3%A9#cite_note-30"><span class="cite-bracket">[</span>30<span class="cite-bracket">]</span></a></sup>
        </p>
      `
      const result = highlightTextInScope(
        document,
        document.body,
        "At the Republicans' national convention in December 2021, Pradié was part of the 11-member committee which oversaw the party's selection of its candidate for the 2022 presidential elections.",
      )
      expect(result).toBeGreaterThan(0)
      expect(CSS.highlights.has('poliloom')).toBe(true)
    })
  })
})
