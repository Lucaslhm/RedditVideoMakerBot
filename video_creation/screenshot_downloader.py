import json
import re
from pathlib import Path
from typing import Dict, Final

import translators
from playwright.async_api import async_playwright
from playwright.sync_api import ViewportSize
from rich.progress import track

from utils import settings
from utils.console import print_step, print_substep
from utils.imagenarator import imagemaker
from utils.playwright import clear_cookie_by_name

from utils.videos import save_data

__all__ = ["get_screenshots_of_reddit_posts"]

async def get_screenshots_of_reddit_posts(reddit_object: dict, screenshot_num: int):
    """Downloads screenshots of reddit posts as seen on the web. Downloads to assets/temp/png.

    Args:
        reddit_object (Dict): Reddit object received from reddit/subreddit.py
        screenshot_num (int): Number of screenshots to download
    """
    # settings values
    W: Final[int] = int(settings.config["settings"]["resolution_w"])
    H: Final[int] = int(settings.config["settings"]["resolution_h"])
    lang: Final[str] = settings.config["reddit"]["thread"]["post_lang"]
    storymode: Final[bool] = settings.config["settings"]["storymode"]

    print_step("Downloading screenshots of reddit posts...")
    reddit_id = re.sub(r"[^\w\s-]", "", reddit_object["thread_id"])
    # ! Make sure the reddit screenshots folder exists
    Path(f"assets/temp/{reddit_id}/png").mkdir(parents=True, exist_ok=True)

    cookie_file = open(
        f"./video_creation/data/cookie-{'dark-mode' if settings.config['settings']['theme'] == 'dark' else 'light-mode'}.json", 
        encoding="utf-8"
    )
    bgcolor = (33, 33, 36, 255) if settings.config["settings"]["theme"] == "dark" else (255, 255, 255, 255)
    txtcolor = (240, 240, 240) if settings.config["settings"]["theme"] == "dark" else (0, 0, 0)
    transparent = settings.config["settings"]["theme"] == "transparent" and storymode

    if storymode and settings.config["settings"]["storymodemethod"] == 1:
        # for idx,item in enumerate(reddit_object["thread_post"]):
        print_substep("Generating images...")
        return imagemaker(
            theme=bgcolor,
            reddit_obj=reddit_object,
            txtclr=txtcolor,
            transparent=transparent,
        )

    async with async_playwright() as p:
        print_substep("Launching Headless Browser...")
        browser = await p.chromium.launch(headless=True)
        dsf = (W // 600) + 1

        context = await browser.new_context(
            locale=lang or "en-us",
            color_scheme="dark",
            viewport=ViewportSize(width=W, height=H),
            device_scale_factor=dsf,
        )
        cookies = json.load(cookie_file)
        cookie_file.close()
        await context.add_cookies(cookies)

        context.add_cookies(cookies)  # load preference cookies

        # Login to Reddit
        print_substep("Logging in to Reddit...")
        page = await context.new_page()
        await page.goto("https://www.reddit.com/login", timeout=0)
        await page.set_viewport_size(ViewportSize(width=1920, height=1080))
        await page.wait_for_load_state()
        await page.locator('[name="username"]').fill(settings.config["reddit"]["creds"]["username"])
        await page.locator('[name="password"]').fill(settings.config["reddit"]["creds"]["password"])
        await page.locator("button[class$='m-full-width']").click()
        await page.wait_for_timeout(5000)

        login_error_div = page.locator(".AnimatedForm__errorMessage").first
        if await login_error_div.is_visible():
            login_error_message = await login_error_div.inner_text()
            if login_error_message.strip() == "":
                # The div element is empty, no error
                pass
            else:
                # The div contains an error message
                print_substep(
                    "Your reddit credentials are incorrect! Please modify them accordingly in the config.toml file.",
                    style="red",
                )
                exit()
        else:
            pass

        page.wait_for_load_state()
        # Handle the redesign
        # Check if the redesign optout cookie is set
        if page.locator("#redesign-beta-optin-btn").is_visible():
            await clear_cookie_by_name(context, "redesign_optout")
            await page.reload()

        await page.goto(reddit_object["thread_url"], timeout=0)
        await page.set_viewport_size(ViewportSize(width=W, height=H))
        await page.wait_for_load_state()
        await page.wait_for_timeout(5000)

        if await page.locator(
            "#t3_12hmbug > div > div._3xX726aBn29LDbsDtzr_6E._1Ap4F5maDtT1E1YuCiaO0r.D3IL3FD0RFy_mkKLPwL4 > div > div > button"
        ).is_visible():
            await page.locator(
                "#t3_12hmbug > div > div._3xX726aBn29LDbsDtzr_6E._1Ap4F5maDtT1E1YuCiaO0r.D3IL3FD0RFy_mkKLPwL4 > div > div > button"
            ).click()
            await page.wait_for_load_state()

        if await page.locator(
            "#SHORTCUT_FOCUSABLE_DIV > div:nth-child(7) > div > div > div > header > div > div._1m0iFpls1wkPZJVo38-LSh > button > i"
        ).is_visible():
            await page.locator(
                "#SHORTCUT_FOCUSABLE_DIV > div:nth-child(7) > div > div > div > header > div > div._1m0iFpls1wkPZJVo38-LSh > button > i"
            ).click()

        if lang:
            print_substep("Translating post...")
            texts_in_tl = translators.translate_text(
                reddit_object["thread_title"],
                to_language=lang,
                translator="google",
            )
            await page.evaluate(
                "tl_content => document.querySelector('[data-adclicklocation=\"title\"] > div > div > h1').textContent = tl_content",
                texts_in_tl,
            )
        else:
            print_substep("Skipping translation...")

        postcontentpath = f"assets/temp/{reddit_id}/png/title.png"
        try:
            if settings.config["settings"]["zoom"] != 1:
                # store zoom settings
                zoom = settings.config["settings"]["zoom"]
                await page.evaluate("document.body.style.zoom=" + str(zoom))
                location = await page.locator('[data-test-id="post-content"]').bounding_box()
                for i in location:
                    location[i] = float("{:.2f}".format(location[i] * zoom))
                await page.screenshot(clip=location, path=postcontentpath)
            else:
                await page.locator('[data-test-id="post-content"]').screenshot(path=postcontentpath)
        except Exception as e:
            print_substep("Something went wrong!", style="red")
            resp = input("Something went wrong with making the screenshots! Do you want to skip the post? (y/n) ")
            if resp.casefold().startswith("y"):
                save_data("", "", "skipped", reddit_id, "")
                print_substep("The post is successfully skipped! You can now restart the program and this post will be skipped.", "green")
                resp = input("Do you want the error traceback for debugging purposes? (y/n)")
                if not resp.casefold().startswith("y"):
                    exit()
                raise e

        if storymode:
            await page.locator('[data-click-id="text"]').first.screenshot(path=f"assets/temp/{reddit_id}/png/story_content.png")
        else:
            for idx, comment in enumerate(track(reddit_object["comments"][:screenshot_num], "Downloading screenshots...")):
                if idx >= screenshot_num:
                    break
                if await page.locator('[data-testid="content-gate"]').is_visible():
                    await page.locator('[data-testid="content-gate"] button').click()
                await page.goto(f'https://reddit.com{comment["comment_url"]}', timeout=0)
                if settings.config["reddit"]["thread"]["post_lang"]:
                    comment_tl = translators.translate_text(comment["comment_body"], translator="google", to_language=settings.config["reddit"]["thread"]["post_lang"])
                    await page.evaluate('([tl_content, tl_id]) => document.querySelector(`#t1_${tl_id} > div:nth-child(2) > div > div[data-testid="comment"] > div`).textContent = tl_content', [comment_tl, comment["comment_id"]])
                try:
                    if settings.config["settings"]["zoom"] != 1:
                        zoom = settings.config["settings"]["zoom"]
                        await page.evaluate("document.body.style.zoom=" + str(zoom))
                        await page.locator(f"#t1_{comment['comment_id']}").scroll_into_view_if_needed()
                        location = await page.locator(f"#t1_{comment['comment_id']}").bounding_box()
                        for i in location:
                            location[i] = float("{:.2f}".format(location[i] * zoom))
                        await page.screenshot(clip=location, path=f"assets/temp/{reddit_id}/png/comment_{idx}.png")
                    else:
                        await page.locator(f"#t1_{comment['comment_id']}").screenshot(path=f"assets/temp/{reddit_id}/png/comment_{idx}.png")
                except TimeoutError:
                    del reddit_object["comments"]
                    screenshot_num += 1
                    print("TimeoutError: Skipping screenshot...")
                    continue
        await browser.close()
    print_substep("Screenshots downloaded Successfully.", style="bold green")
