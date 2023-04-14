import json
import random
import configparser
from anticaptchaofficial.hcaptchaproxyless import hCaptchaProxyless
from python_anticaptcha import AnticaptchaClient, HCaptchaTaskProxyless

config = configparser.ConfigParser()
config.read('settings/config.ini', encoding="utf-8")

api_keys = json.loads(config.get("hcaptcha", "anticaptcha_api_key"))


def hcaptcha_official_solver(api_key, url, site_key):
    solver = hCaptchaProxyless()
    solver.set_verbose(1)
    solver.set_key(api_key)
    solver.set_website_url(url)
    solver.set_website_key(site_key)
    solver.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/87.0.4280.88 Safari/537.36")
    solver.set_soft_id(0)

    g_response = solver.solve_and_return_solution()
    if g_response != 0:
        return g_response
    else:
        print("task finished with error " + solver.error_code)
        return None


def hcaptcha_anticaptcha_solver(api_key, url, site_key):
    client = AnticaptchaClient(api_key)
    task = HCaptchaTaskProxyless(website_url=url, website_key=site_key)
    try:
        job = client.createTaskSmee(task, timeout=10 * 60)
        return job.get_solution_response()
    except ValueError as e:
        print(e)
        return None


def hcaptcha_solver(url, site_key):
    print("Using Anticaptcha Client !!!")
    api_key = random.choice(api_keys)
    result = hcaptcha_anticaptcha_solver(api_key, url, site_key)
    if not result:
        result = hcaptcha_official_solver(api_key, url, site_key)
    return result
