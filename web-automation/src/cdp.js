/**
 * Navigate to URL and capture page data
 * @param {import('puppeteer-core').Browser} browser
 * @param {string} url
 * @returns {Promise<object>}
 */
export async function navigateAndValidate(browser, url) {
  const page = await browser.newPage();

  const networkRequests = [];
  let mainDocumentStatus = null;

  // Capture network responses
  page.on('response', response => {
    const reqUrl = response.url();
    const status = response.status();
    const contentType = response.headers()['content-type'] || '';

    networkRequests.push({
      url: reqUrl,
      status,
      contentType,
    });

    // Track main document status
    if (reqUrl === url || reqUrl === url + '/' || reqUrl.replace(/\/$/, '') === url.replace(/\/$/, '')) {
      if (contentType.includes('text/html')) {
        mainDocumentStatus = status;
      }
    }
  });

  // Navigate
  const startTime = Date.now();
  let response;
  try {
    response = await page.goto(url, {
      waitUntil: 'networkidle0',
      timeout: 30000,
    });
  } catch (err) {
    await page.close();
    throw new Error(`Navigation failed: ${err.message}`);
  }
  const loadTime = Date.now() - startTime;

  // Capture page data
  const finalUrl = page.url();
  const title = await page.title();
  const html = await page.content();

  // Take screenshot
  const screenshot = await page.screenshot({
    fullPage: true,
    encoding: 'base64',
  });

  await page.close();

  return {
    requestedUrl: url,
    finalUrl,
    title,
    httpStatus: response?.status() || mainDocumentStatus || null,
    loadTimeMs: loadTime,
    networkRequests,
    html,
    screenshot,
    timestamp: new Date().toISOString(),
  };
}
