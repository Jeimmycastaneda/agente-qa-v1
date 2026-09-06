"""Conector opcional para explorar un cotizador web y obtener evidencia de navegación.

No guarda credenciales en disco. Playwright se importa de forma diferida para que
Agente QA siga funcionando sin navegador cuando esta integración no se usa.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin


class CotizadorBrowserError(RuntimeError):
    pass


@dataclass
class CotizadorInspection:
    source_text: str
    pages: list[str]


def inspect_cotizador(url: str, username: str, password: str, login_selector: str = "") -> CotizadorInspection:
    """Inicia sesión, recorre enlaces visibles y devuelve evidencia textual.

    ``login_selector`` es opcional: si se informa, se pulsa después de llenar
    usuario/clave. Los selectores por defecto cubren formularios habituales.
    No se realizan acciones de negocio ni envíos distintos del login.
    """
    if not url.strip():
        raise CotizadorBrowserError("Debe indicar la URL del cotizador.")
    if not username.strip() or not password:
        raise CotizadorBrowserError("Debe indicar usuario y contraseña.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CotizadorBrowserError(
            "La integración web requiere Playwright. Instálelo con 'pip install playwright' "
            "y luego ejecute 'playwright install chromium'."
        ) from exc

    pages: list[str] = []
    chunks: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.locator("input[type='text'], input[type='email'], input[name*='user' i], input[name*='usuario' i]").first.fill(username)
            page.locator("input[type='password'], input[name*='pass' i], input[name*='clave' i]").first.fill(password)
            if login_selector.strip():
                page.locator(login_selector).click()
            else:
                page.locator("button[type='submit'], input[type='submit']").first.click()
            page.wait_for_load_state("domcontentloaded", timeout=30000)

            for _ in range(8):
                current = page.url
                if current not in pages:
                    pages.append(current)
                body = page.locator("body").inner_text(timeout=10000)
                links = page.locator("a:visible, button:visible")
                labels = []
                for index in range(min(links.count(), 80)):
                    text = links.nth(index).inner_text().strip()
                    if text and text not in labels:
                        labels.append(text)
                chunks.append(
                    f"URL: {current}\nELEMENTOS VISIBLES: "
                    + " | ".join(labels)
                    + f"\nCONTENIDO VISIBLE:\n{body[:12000]}"
                )
                navigable = page.locator("a:visible[href]")
                target = None
                for index in range(min(navigable.count(), 40)):
                    href = navigable.nth(index).get_attribute("href") or ""
                    text = navigable.nth(index).inner_text().strip()
                    if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue
                    absolute = urljoin(current, href)
                    if absolute.startswith(url.split("/")[0] + "//") and absolute not in pages:
                        target = absolute
                        break
                if not target:
                    break
                page.goto(target, wait_until="domcontentloaded", timeout=30000)

        except Exception as exc:
            raise CotizadorBrowserError(f"No fue posible explorar el cotizador: {exc}") from exc
        finally:
            browser.close()

    source = (
        "EVIDENCIA DEL COTIZADOR WEB (solo para derivar navegación y pasos; "
        "no asumir reglas de negocio no visibles).\n\n"
        + "\n\n---\n\n".join(chunks)
    )
    return CotizadorInspection(source_text=source, pages=pages)
