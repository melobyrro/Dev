/**
 * Run assertions against captured page data
 * @param {object} result - Result from navigateAndValidate
 * @param {object} assertions - Assertion config
 * @param {string} [assertions.text] - Text to find in page
 * @param {string} [assertions.selector] - CSS selector to find
 * @param {string} [assertions.regex] - Regex pattern to match
 * @returns {Promise<Array<{type: string, expected: string, passed: boolean, message: string}>>}
 */
export async function runAssertions(result, assertions) {
  const results = [];

  // Text assertion
  if (assertions.text) {
    const found = result.html.includes(assertions.text);
    results.push({
      type: 'text',
      expected: assertions.text,
      passed: found,
      message: found
        ? `Text found: "${assertions.text}"`
        : `Text NOT found: "${assertions.text}"`,
    });
  }

  // Selector assertion
  if (assertions.selector) {
    const selectorExists = checkSelectorInHtml(result.html, assertions.selector);
    results.push({
      type: 'selector',
      expected: assertions.selector,
      passed: selectorExists,
      message: selectorExists
        ? `Selector found: "${assertions.selector}"`
        : `Selector NOT found: "${assertions.selector}"`,
    });
  }

  // Regex assertion
  if (assertions.regex) {
    let found = false;
    let errorMsg = null;
    try {
      const regex = new RegExp(assertions.regex);
      found = regex.test(result.html);
    } catch (err) {
      errorMsg = `Invalid regex: ${err.message}`;
    }

    results.push({
      type: 'regex',
      expected: assertions.regex,
      passed: found && !errorMsg,
      message: errorMsg
        ? errorMsg
        : found
          ? `Regex matched: "${assertions.regex}"`
          : `Regex did NOT match: "${assertions.regex}"`,
    });
  }

  return results;
}

/**
 * Check if a CSS selector likely exists in HTML
 * This is a simple heuristic - for production, use cheerio or similar
 * @param {string} html
 * @param {string} selector
 * @returns {boolean}
 */
function checkSelectorInHtml(html, selector) {
  // ID selector: #foo
  if (selector.startsWith('#')) {
    const id = selector.slice(1).split(/[.\s\[>+~]/)[0]; // Extract ID part
    return html.includes(`id="${id}"`) || html.includes(`id='${id}'`);
  }

  // Class selector: .foo
  if (selector.startsWith('.')) {
    const className = selector.slice(1).split(/[.\s\[>+~]/)[0]; // Extract class part
    // Look for class attribute containing this class name
    const classRegex = new RegExp(`class=["'][^"']*\\b${escapeRegex(className)}\\b[^"']*["']`);
    return classRegex.test(html);
  }

  // Attribute selector: [data-foo] or [data-foo="bar"]
  if (selector.startsWith('[')) {
    const match = selector.match(/^\[([^\]=]+)(?:="([^"]+)")?\]/);
    if (match) {
      const [, attr, value] = match;
      if (value) {
        return html.includes(`${attr}="${value}"`) || html.includes(`${attr}='${value}'`);
      }
      return html.includes(`${attr}=`) || html.includes(`${attr} `);
    }
  }

  // Tag selector: div, span, etc.
  const tag = selector.split(/[.\s\[#>+~]/)[0].toLowerCase();
  if (tag && /^[a-z][a-z0-9]*$/i.test(tag)) {
    return html.toLowerCase().includes(`<${tag}`) || html.toLowerCase().includes(`<${tag.toLowerCase()}`);
  }

  // Complex selector - just check if any part exists
  console.error(`[Assertion] Complex selector "${selector}" - using basic check`);
  return html.includes(selector);
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
