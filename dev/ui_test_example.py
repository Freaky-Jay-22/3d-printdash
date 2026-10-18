# Example Playwright UI test (brands, spool dialog, AMS chip). Usage: python3 ui_test_example.py <screenshot-dir>
import asyncio, sys
from playwright.async_api import async_playwright
S = sys.argv[1]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 900}, color_scheme="dark")
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        await pg.goto("http://localhost:8090/"); await pg.wait_for_timeout(5000)
        await pg.locator(".card", has_text="X1C").first.screenshot(path=f"{S}/ui_ams_card.png")
        await pg.click("nav.tabs >> text=Filament"); await pg.wait_for_timeout(1500)
        await pg.click("#filament-subtabs >> text=Marken"); await pg.wait_for_timeout(500)
        await pg.screenshot(path=f"{S}/ui_brands.png", full_page=True)
        await pg.locator(".brand-card", has_text="Bambu Lab").locator("[aria-label=Bearbeiten]").click(); await pg.wait_for_timeout(500)
        await pg.locator("#brand-dialog").screenshot(path=f"{S}/ui_brand_dialog.png")
        await pg.click("#brand-dialog >> text=Abbrechen")
        # quick entry
        await pg.locator(".brand-card", has_text="Bambu Lab").locator("text=+ Filament dieser Marke").click(); await pg.wait_for_timeout(400)
        await pg.screenshot(path=f"{S}/dbg.png"); await pg.click("#spool-dialog .cswatch[title^=Red]", timeout=5000); await pg.wait_for_timeout(200)
        await pg.locator("#spool-dialog").screenshot(path=f"{S}/ui_spool_brand.png")
        # new colour typed by hand gets remembered
        await pg.fill("#spool-dialog input[placeholder='z. B. Jade White']", "Sunflower Yellow")
        await pg.click("#spool-dialog >> text=Speichern"); await pg.wait_for_timeout(1500)
        # brand select switch to Elegoo -> materials limited
        await pg.click("#filament-subtabs >> text=Bestand"); await pg.wait_for_timeout(300)
        await pg.click("#filament-summary >> text=+ Filament"); await pg.wait_for_timeout(300)
        await pg.select_option("#spool-dialog .pick-or-type select >> nth=0", "Elegoo"); await pg.wait_for_timeout(200)
        opts = await pg.eval_on_selector_all("#spool-dialog .pick-or-type >> nth=1 >> option", "o => o.map(x => x.textContent)")
        print("elegoo materials:", opts)
        await pg.click("#spool-dialog >> text=Abbrechen")
        await pg.click("nav.tabs >> text=Einstellungen"); await pg.wait_for_timeout(1500)
        await pg.locator(".item", has_text="Bambu Lab (LAN)").first.screenshot(path=f"{S}/ui_ams_settings.png")
        await pg.click("nav.tabs >> text=Übersicht"); await pg.wait_for_timeout(1500)
        await pg.locator(".card", has_text="X1C").first.locator("h2").click(); await pg.wait_for_timeout(1500)
        await pg.locator(".detail-side").screenshot(path=f"{S}/ui_ams_detail.png")
        m = await b.new_page(viewport={"width": 390, "height": 844}, color_scheme="light")
        await m.goto("http://localhost:8090/#filament"); await m.wait_for_timeout(3000)
        await m.click("#filament-subtabs >> text=Marken"); await m.wait_for_timeout(300)
        await m.screenshot(path=f"{S}/ui_brands_phone.png")
        print("errors:", errs)
        await b.close()
asyncio.run(main())
