const { mkdirSync, writeFileSync } = require('fs');
const { resolve } = require('path');
const { pathToFileURL } = require('url');
const puppeteer = require('puppeteer');

(async () => {
	const invisibleCharacters = await getData();
	mkdirSync('./out/', { recursive: true });
	writeFileSync(
		'./out/invisible-characters.json',
		JSON.stringify(invisibleCharacters, null, 2),
		{ encoding: 'utf8' }
	);
})();

async function getData() {
	const browser = await puppeteer.launch({ devtools: true, headless: false });
	const page = await browser.newPage();

	let resolveFinished;
	const finishedPromise = new Promise((resolve) => {
		resolveFinished = resolve;
	});

	await page.exposeFunction('handleData', (invisibleCharacters) => {
		resolveFinished(invisibleCharacters);
	});

	await page.goto(pathToFileURL(resolve(__dirname, './browser-index.html')).href, {
		waitUntil: 'load',
	});
	console.log('loaded');

	const result = await finishedPromise;
	await browser.close();
	return result;
}
