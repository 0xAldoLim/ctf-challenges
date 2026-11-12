const express = require('express');
const puppeteer = require('puppeteer');
const rateLimit = require('express-rate-limit');


const FLAG = process.env.FLAG || 'flag{testflag}';
const DOMAIN = process.env.DOMAIN || 'http://chall/';
const PORT = process.env.PORT || 1337;


const app = express();
app.use(express.json());
app.set('trust proxy', 1);

const reportLimiter = rateLimit({
    windowMs: 1 * 60 * 1000, // 1 minute
    max: 2,
    message: { error: 'Too many requests, please try again later.' }
});


function sleep(ms) {
    return new Promise(res => setTimeout(res, ms));
}

async function visit(url) {
    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
        ],
    });
    console.log('Browser launched');
    console.log('Visiting URL:', url);

    try {
        let page = await browser.newPage()
        await page.goto(DOMAIN, { waitUntil: 'networkidle0' });

        const cookies = [{
            name: 'flag',
            value: FLAG
        }];

        await page.setCookie(...cookies);
        await page.close();

        page = await browser.newPage();
        await page.goto(url, { waitUntil: [] });

        await sleep(3_000);
        // whew... enough of that.
    } catch (err) {
        console.error('Error visiting page:', err);
    } finally {
        await browser.close();
    }
}

app.post('/report', reportLimiter, async (req, res) => {
    const { url } = req.body;

    const PREFIX = DOMAIN
    if (!url || typeof url !== 'string' || !url.startsWith(PREFIX)) {
        return res.status(400).json({ error: `Invalid URL. Url should be a string and start with ${PREFIX}.` });
    }

    try {
        await visit(url);
        res.json({ success: true });
    } catch (err) {
        console.error('Error on /report', err);
        res.status(500).json({ error: 'Failed to visit URL.' });
    }
});

app.get('/', (req, res) => {
    res.sendFile('bot.html', { 'root':__dirname });
})

app.listen(PORT, () => {
    console.log(`Bot is running on port http://127.0.0.1:${PORT}`);
})
