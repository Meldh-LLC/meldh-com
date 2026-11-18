"""Exercise the published layout in a browser before deploying it."""
import argparse
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from playwright.sync_api import expect, sync_playwright


@contextmanager
def local_site(directory):
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory.resolve()))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/"
        finally:
            server.shutdown()
            worker.join()


def check_site(chromium, base, executable):
    browser = chromium.launch(executable_path=executable)
    page = browser.new_page(viewport={"width": 1440, "height": 960}, reduced_motion="reduce")
    try:
        page.goto(urljoin(base, "research/"))
        articles = page.locator(".meldh-feature h3 a").evaluate_all("links => links.map(a => a.href)")
        assert articles, "The Research archive is empty"
        sitemap = page.request.get(urljoin(base, "sitemap.xml"))
        assert sitemap.ok
        published = {
            urlparse(node.text).path for node in ElementTree.fromstring(sitemap.body()).findall(".//{*}loc")
            if "/writing/" in node.text
        }
        assert published == {urlparse(url).path for url in articles}, "Archive and sitemap differ"
        for url in [base, urljoin(base, "research/"), *articles]:
            page.goto(url)
            research = page.locator("header").get_by_role("link", name="Research", exact=True)
            expect(research).to_be_visible()
            assert research.evaluate("a => a.href") == urljoin(base, "research/")
            if url in articles:
                back = page.get_by_role("link", name="All research", exact=True)
                expect(back).to_be_visible()
                assert back.evaluate("link => link.href") == urljoin(base, "research/")
        for width in (320, 390, 768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 800})
            for url in [base, urljoin(base, "research/"), *articles]:
                page.goto(url)
                assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), (url, width)
        page.set_viewport_size({"width": 390, "height": 800})
        page.goto(base)
        page.keyboard.press("Tab")
        expect(page.get_by_role("link", name="Skip to content")).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#main-content")).to_be_focused()
        menu = page.get_by_role("button", name="Menu", exact=True)
        drawer = page.locator(".md-sidebar--primary")
        assert drawer.evaluate("panel => panel.inert")
        menu.focus()
        page.keyboard.press("Enter")
        expect(menu).to_have_attribute("aria-expanded", "true")
        close = drawer.get_by_role("button", name="Close menu")
        expect(close).to_be_focused()
        page.keyboard.press("Tab")
        assert drawer.evaluate("panel => panel.contains(document.activeElement)")
        page.keyboard.press("Escape")
        expect(menu).to_be_focused()
        expect(menu).to_have_attribute("aria-expanded", "false")
        assert drawer.evaluate("panel => panel.inert")
        page.keyboard.press("Space")
        close.click()
        expect(menu).to_be_focused()

        legacy = (
            "chat-template-settings-determine-whether-qwen3s-thinking-mode-survives-fine-tuning",
            "deliberation-measurably-reduces-fabrication-under-false-premises",
        )
        for fragment in legacy:
            page.goto("about:blank")
            page.goto(urljoin(base, f"writing/qwen3-template-thinking/#{fragment}"))
            page.wait_for_function("""id => {
                const heading = document.getElementById(id)?.closest("h1, h2");
                if (!heading) return false;
                const top = heading.getBoundingClientRect().top;
                return top >= document.querySelector("header").getBoundingClientRect().bottom && top < innerHeight;
            }""", arg=fragment)

        page.goto(base)
        search = page.get_by_role("button", name="Search", exact=True)
        search.click()
        query = page.get_by_role("textbox", name="Search")
        query.fill("philosophy")
        result = page.locator(".md-search-result__link").first
        expect(result).to_be_visible()
        destination = result.evaluate("link => link.href")
        result.click()
        expect(page).to_have_url(destination)
    finally:
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--url", help="Check an existing served site instead")
    parser.add_argument("--chrome", help="Use a locally installed Chromium executable")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        if args.url:
            check_site(playwright.chromium, args.url, args.chrome)
        else:
            with local_site(args.site) as address:
                check_site(playwright.chromium, address, args.chrome)
    print("Navigation and responsive browser checks passed.")
