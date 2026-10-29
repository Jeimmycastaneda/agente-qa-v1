"""Conector de navegación restringido al módulo Colectivos Autos/Cotización.

No guarda credenciales. La navegación solo sigue enlaces visibles que aporten
evidencia del módulo autorizado y filtra el texto visible para no entregar
información de otros módulos al agente.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

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

def _origin(value: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    return parsed.scheme.casefold(), parsed.netloc.casefold()

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

                page_title = page.title()

                frame_info = []
                for frame in page.frames:
                    frame_info.append(
                        f"Nombre: {frame.name or '(sin nombre)'}; "
                        f"URL: {frame.url}"
                    )

                body_text = page.locator("body").inner_text(timeout=10000)

                page_info = page.evaluate("""() => ({
                    htmlLength: document.documentElement.outerHTML.length,
                    forms: Array.from(document.forms).map(f => ({
                        action: f.action,
                        method: f.method
                    })),
                    controls: Array.from(
                        document.querySelectorAll(
                            'input, button, select, a, iframe'
                        )
                    ).map(e => ({
                        tag: e.tagName,
                        type: e.type || '',
                        text: (e.innerText || e.value || '').trim(),
                        id: e.id || '',
                        name: e.name || '',
                        href: e.href || '',
                        visible: !!(e.offsetWidth || e.offsetHeight)
                    })).slice(0, 40)
                })""")


                diagnostic = (
                    f"TITULO DE LA PAGINA: {page_title}\n"
                    f"LONGITUD DEL TEXTO VISIBLE: {len(body_text)} caracteres\n"
                    f"TEXTO VISIBLE: {body_text[:500]!r}\n"
                    f"ESTADO DOCUMENTO: "
                    f"{page.evaluate('document.readyState')}\n"
                    f"URL FINAL: {page.url}\n"
                    "FRAMES DETECTADOS:\n"
                    + "\n".join(frame_info[:20])
                    + f"\nDIAGNOSTICO HTML Y CONTROLES:\n{page_info}\n"
                )




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
                            f"Nombre: {visible_name}; Tipo: {element.evaluate('el => el.tagName')}; "
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
                                f"Control: {value}; Tipo: {element.get_attribute('type') or element.evaluate('el => el.tagName')}"
                            )

                body = page.locator("body").inner_text(timeout=10000)
                scoped_body = [
                    line.strip()
                    for line in body.splitlines()
                    if line.strip() and _in_scope(line)
                ]

                chunks.append(
                    f"URL: {current}\n"
                    + diagnostic + "\n"
                    "ELEMENTOS DE NAVEGACION VISIBLES:\n"
                    + "\n".join(navigation_items[:120])
                    + "\nENCABEZADOS/PANTALLAS VISIBLES:\n"
                    + "\n".join(headings[:50])
                    + "\nCONTROLES VISIBLES RELEVANTES:\n"
                    + "\n".join(controls[:80])
                    + "\nEVIDENCIA VISIBLE DEL MODULO COLECTIVOS AUTOS:\n"
                    + "\n".join(scoped_body[:250])
                )





                navigable = page.locator("a[href]")

                print("[QA DEBUG] URL:", page.url)
                print(
                    "[QA DEBUG] Enlaces del menú:",
                    page.locator("a[href]").evaluate_all(
                        """els => els.map(a => ({
                            texto: (a.innerText || '').trim(),
                            href: a.getAttribute('href'),
                            visible: !!(a.offsetWidth || a.offsetHeight)
                        }))"""
                    ),
                )

                target = None

                allowed_host = (
                    "colectivoautos2.pruebasrentec.cotizadoresgenerales.com"
                )
                allowed_paths = {
                    "/app/crearcotizacioncolectivo",
                    "/app/consultarcotizacion",
                    "/app/revisiondelegacion",
                }



                for index in range(navigable.count()):
                    link = navigable.nth(index)

                    href = link.get_attribute("href") or ""
                    print(
                        "[QA DEBUG] ENLACE:",
                        index,
                        "VISIBLE_PLAYWRIGHT:",
                        link.is_visible(),
                        "HREF:",
                        href,
                    )

                    href = link.get_attribute("href") or ""
                    label = link.inner_text().strip()
                    element_id = link.get_attribute("id") or ""

                    if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue

                    absolute = urljoin(current, href)
                    parsed_target = urlsplit(absolute)
                    host = (parsed_target.hostname or "").casefold()
                    path = parsed_target.path.casefold().rstrip("/")
                    is_https = parsed_target.scheme.casefold() == "https"

                    is_colectivos_link = (
                        host == allowed_host
                        and is_https
                        and parsed_target.path in ("", "/")
                        and bool(parsed_target.query)
                        and _origin(current) == _origin(url)
                    )

                    is_allowed_page = (
                        host == allowed_host
                        and is_https
                        and path in {
                            "/app/crearcotizacioncolectivo",
                            "/app/consultarcotizacion",
                            "/app/revisiondelegacion",
                        }
                    )

                    is_same_origin_scoped = (
                        _origin(absolute) == _origin(url)
                        and (_in_scope(label) or _in_scope(href))
                    )

                    print(
                        "[QA DEBUG] ENLACE VISIBLE:",
                        repr(label),
                        "RUTA:",
                        path,
                        "PERMITIDA:",
                        is_allowed_page,
                    )

                    rutas_colectivos = {
                        "/app/crearcotizacioncolectivo",
                        "/app/consultarcotizacion",
                        "/app/revisiondelegacion",
                    }

                    es_ruta_colectivos = (
                        host == allowed_host
                        and is_https
                        and path in rutas_colectivos
                    )

                    if not (
                        is_colectivos_link
                        or is_allowed_page
                        or is_same_origin_scoped
                        or es_ruta_colectivos
                    ):
                        print(
                            "[QA DEBUG] ENLACE DESCARTADO:",
                            repr(label),
                            "URL:",
                            absolute.split("?")[0],
                        )
                        continue

                    print(
                        "[QA DEBUG] ENLACE ACEPTADO:",
                        repr(label),
                        "URL:",
                        absolute.split("?")[0],
                    )

                    if absolute not in pages:
                        target = absolute
                        break

                print(f"[QA DEBUG] URL actual: {current}")
                print(f"[QA DEBUG] Enlace encontrado: {target is not None}")
                print(f"[QA DEBUG] Enlace seleccionado: {target}")

                if not target:
                    break




                chunks.append(
                    f"ENLACE SELECCIONADO PARA NAVEGAR: {target}\n"
                )

                print(f"[QA DEBUG] Enlace seleccionado: {target}")
                page.goto(
                    target,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )


                print("[QA DEBUG] URL después de goto:", page.url)
                print("[QA DEBUG] Título:", page.title())
                print("[QA DEBUG] Estado HTTP: pendiente de validar")
                print("[QA DEBUG] HTML:", page.locator("body").inner_text()[:1500])
                print("[QA DEBUG] Enlaces encontrados:", page.locator("a").count())

                chunks.append(
                    f"URL DESPUES DE NAVEGAR: {page.url}\n"
                    f"TITULO DESPUES DE NAVEGAR: {page.title()}\n"
                    f"TEXTO DESPUES DE NAVEGAR: "
                    f"{page.locator('body').inner_text(timeout=10000)[:500]!r}\n"
                )




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
