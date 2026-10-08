"""Conector de navegación restringido al módulo Colectivos Autos/Cotización.

No guarda credenciales. La navegación solo sigue enlaces visibles que aporten
evidencia del módulo autorizado y filtra el texto visible para no entregar
información de otros módulos al agente.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin


class CotizadorColectivosError(RuntimeError):
    pass


@dataclass
class CotizadorInspection:
    source_text: str
    pages: list[str]


_SCOPE = ("colectivos", "autos colectivos", "cotización", "cotizacion", "cotizadores web")


def _in_scope(value: str) -> bool:
    normalized = (value or "").casefold()
    return any(term in normalized for term in _SCOPE)


def inspect_cotizador_colectivos(
    url: str,
    username: str,
    password: str,
    login_selector: str = "",
) -> CotizadorInspection:
    if not url.strip():
        raise CotizadorColectivosError("Debe indicar la URL del cotizador.")
    if not username.strip() or not password:
        raise CotizadorColectivosError("Debe indicar usuario y contraseña.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CotizadorColectivosError(
            "La integración web requiere Playwright. Instale Playwright y Chromium."
        ) from exc

    pages: list[str] = []
    chunks: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.locator(
                "input[type='text'], input[type='email'], "
                "input[name*='user' i], input[name*='usuario' i]"
            ).first.fill(username)
            page.locator(
                "input[type='password'], input[name*='pass' i], input[name*='clave' i]"
            ).first.fill(password)
            if login_selector.strip():
                page.locator(login_selector).click()
            else:
                page.locator("button[type='submit'], input[type='submit']").first.click()
            page.wait_for_load_state("domcontentloaded", timeout=30000)

            for _ in range(8):
                current = page.url
                if current not in pages:
                    pages.append(current)

                # Capturar evidencia de navegación con mayor precisión, sin salir del alcance autorizado.
                links = page.locator("a:visible, button:visible")
                scoped_labels = []
                navigation_items = []
                for index in range(min(links.count(), 150)):
                    element = links.nth(index)
                    label = element.inner_text().strip()
                    aria = (element.get_attribute("aria-label") or "").strip()
                    title = (element.get_attribute("title") or "").strip()
                    href = (element.get_attribute("href") or "").strip()
                    visible_name = label or aria or title
                    if not visible_name:
                        continue
                    if _in_scope(visible_name) or _in_scope(href):
                        if visible_name not in scoped_labels:
                            scoped_labels.append(visible_name)
                        navigation_items.append(
                            f"Nombre: {visible_name}; Tipo: {element.evaluate(\"el => el.tagName\")}; "
                            f"Destino: {href or 'acción visible sin enlace'}"
                        )

                headings = []
                for selector in ("h1:visible", "h2:visible", "h3:visible", "[role='heading']:visible"):
                    locator = page.locator(selector)
                    for index in range(min(locator.count(), 30)):
                        text_value = locator.nth(index).inner_text().strip()
                        if text_value and text_value not in headings:
                            headings.append(text_value)

                controls = []
                for selector in ("input:visible", "select:visible", "textarea:visible"):
                    locator = page.locator(selector)
                    for index in range(min(locator.count(), 80)):
                        element = locator.nth(index)
                        name = (element.get_attribute("name") or "").strip()
                        aria = (element.get_attribute("aria-label") or "").strip()
                        placeholder = (element.get_attribute("placeholder") or "").strip()
                        value = name or aria or placeholder
                        if value and (_in_scope(value) or _in_scope(element.get_attribute("id") or "")):
                            controls.append(
                                f"Control: {value}; Tipo: {element.get_attribute('type') or element.evaluate(\"el => el.tagName\")}"
                            )

                body = page.locator("body").inner_text(timeout=10000)
                scoped_body = [
                    line.strip()
                    for line in body.splitlines()
                    if line.strip() and _in_scope(line)
                ]

                chunks.append(
                    f"URL: {current}\n"
                    "ELEMENTOS DE NAVEGACION VISIBLES:\n"
                    + "\n".join(navigation_items[:120])
                    + "\nENCABEZADOS/PANTALLAS VISIBLES:\n"
                    + "\n".join(headings[:50])
                    + "\nCONTROLES VISIBLES RELEVANTES:\n"
                    + "\n".join(controls[:80])
                    + "\nEVIDENCIA VISIBLE DEL MODULO COLECTIVOS AUTOS:\n"
                    + "\n".join(scoped_body[:250])
                )

                navigable = page.locator("a:visible[href]")
                target = None
                for index in range(min(navigable.count(), 60)):
                    href = navigable.nth(index).get_attribute("href") or ""
                    label = navigable.nth(index).inner_text().strip()
                    if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue
                    if not _in_scope(label) and not _in_scope(href):
                        continue
                    absolute = urljoin(current, href)
                    if absolute.startswith(url.split("/")[0] + "//") and absolute not in pages:
                        target = absolute
                        break

                if not target:
                    break
                page.goto(target, wait_until="domcontentloaded", timeout=30000)

        except Exception as exc:
            raise CotizadorColectivosError(
                f"No fue posible explorar el módulo Colectivos Autos: {exc}"
            ) from exc
        finally:
            browser.close()

    source = (
        "EVIDENCIA DE NAVEGACION DEL AMBIENTE REAL — SOLO MODULO COLECTIVOS AUTOS/COTIZACION.\n"
        "Esta evidencia solo sirve para ruta, nombres visibles y pasos de acceso; "
        "no es fuente de reglas funcionales.\n\n"
        + "\n\n---\n\n".join(chunks)
    )
    return CotizadorInspection(source_text=source, pages=pages)
