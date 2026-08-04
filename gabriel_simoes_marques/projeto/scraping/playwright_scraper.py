from playwright.async_api import async_playwright
import asyncio
import trafilatura

async def scrape_url_js(url: str) -> str | None:
	async with async_playwright() as p: 
		browser = await p.chromium.launch(headless=True)
		page =  await browser.new_page()
		await page.goto(url, timeout=20000)
		await page.wait_for_load_state("networkidle")
		content = await page.content()
		await browser.close()
		extracted = trafilatura.extract(content)
	return extracted

if __name__ == "__main__":
	result = asyncio.run(scrape_url_js("https://www.creditas.com/carreiras/"))
	print(result)
