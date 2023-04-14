import os
import asyncio
from flask import request, Flask, \
    render_template, jsonify, redirect
from playwright.async_api import Playwright, \
    async_playwright, expect

app = Flask(__name__)
host = "0.0.0.0"
port = 9001
token = None
company_name = "Anticaptcha-Blaze"
API_ALLOWED_IPS = ['0.0.0.0', '127.0.0.1']

user_dir = 'tmp/playwright'
user_dir = os.path.join(os.getcwd(), user_dir)


@app.route("/", methods=['GET'])
def index():
    return redirect("/hcaptcha")


@app.route("/hcaptcha", methods=['GET'])
def get_hcaptcha():
    ip = request.access_route[-1]
    ip_addr = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ip_addr not in API_ALLOWED_IPS:
        return redirect("https://t.me/cleitonLC")
    return render_template('hcaptcha.html',
                           request={"company_name": company_name})


@app.route("/success", methods=['GET'])
def success():
    response_dict = request.args.to_dict()
    hcaptcha_key = response_dict.get("captcha")
    print(hcaptcha_key)
    return render_template('success.html',
                           request={"company_name": company_name})


@app.route('/hcaptcha/token', methods=['GET'])
def solve_captcha():
    global token

    async def run(playwright: Playwright) -> None:
        global token
        browser = await playwright.firefox.launch(
            args=['--disable-blink-features=AutomationControlled'],
            headless=True
        )
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(f"http://{host}:{port}/hcaptcha", wait_until='domcontentloaded')
        await page.frame_locator("center iframe").locator("div[role=\"checkbox\"]").click()
        token = await page.locator('#textarea').text_content()

        while True:
            await asyncio.sleep(2)
            break

        await page.close()
        await browser.close()

    async def main() -> None:
        async with async_playwright() as playwright:
            await run(playwright)
    try:
        asyncio.run(main())
    except:
        token = None
    return jsonify({"x-captcha-response": token})


app.run(host=host,
        port=port,
        debug=True)
