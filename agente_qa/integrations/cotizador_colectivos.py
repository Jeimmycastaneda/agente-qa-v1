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

                links = page.locator("a:visible, button:visible")
                scoped_labels = []
                for index in range(min(links.count(), 100)):
                    label = links.nth(index).inner_text().strip()
                    if label and _in_scope(label) and label not in scoped_labels:
                        scoped_labels.append(label)

                body = page.locator("body").inner_text(timeout=10000)
                scoped_body = [
                    line.strip()
                    for line in body.splitlines()
                    if line.strip() and _in_scope(line)
                ]

                chunks.append(
                    f"URL: {current}\n"
                    "ELEMENTOS VISIBLES DEL MODULO COLECTIVOS AUTOS: "
                    + " | ".join(scoped_labels)
                    + "\nEVIDENCIA VISIBLE DEL MODULO:\n"
                    + "\n".join(scoped_body[:200])
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
