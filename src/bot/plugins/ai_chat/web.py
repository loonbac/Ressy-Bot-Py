from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from collections import defaultdict, deque
from html.parser import HTMLParser
from math import ceil
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import httpx

# ---------------------------------------------------------------------------
# Tool de navegación web para la IA.
#
# La IA puede pedir leer una página pública. El flujo:
#   1. Validación SSRF: solo http/https, se resuelve el host y se rechazan IPs
#      privadas, loopback, link-local y reservadas (evita que un usuario haga
#      que el bot golpee servicios internos / metadata de la nube).
#   2. httpx con headers de navegador (muchos sitios devuelven 403 a clientes
#      "pelados"). Sigue redirecciones.
#   3. Si httpx falla o la página viene casi vacía (render por JS), se reintenta
#      con Playwright/Chromium headless (ya es dependencia del scraper).
#   4. El HTML se reduce a texto legible (título + cuerpo, sin script/style/nav).
# ---------------------------------------------------------------------------

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_BROWSER_HEADERS = {
    "User-Agent": _DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    # Solo gzip/deflate: httpx no trae brotli/zstd por defecto y, si los
    # anunciamos, algunos servidores comprimen con br y recibimos basura.
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="124", "Not-A.Brand";v="99"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Elementos cuyo contenido nunca es texto legible para el usuario.
# OJO: `head` NO va aquí — su único texto útil es <title>, que capturamos aparte;
# meterlo bloquearía la captura del título. script/style/etc se saltan solos.
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "iframe", "canvas"}
# Elementos de bloque: forzamos salto de línea al cerrarlos para no pegar palabras.
_BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer", "main", "aside", "nav",
    "ul", "ol", "li", "table", "tr", "br", "hr", "blockquote", "pre", "figure",
    "h1", "h2", "h3", "h4", "h5", "h6", "dl", "dt", "dd", "form", "fieldset",
}

WEB_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": (
                "Visita una página web pública por su URL y devuelve su contenido legible "
                "(título y texto principal, sin scripts ni menús). Úsala cuando el usuario "
                "comparta un enlace o pida revisar/resumir/explicar una página o noticia de "
                "internet. Solo http/https y sitios públicos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL completa de la página, incluyendo http:// o https://.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Máximo de caracteres de texto a devolver (1000-20000).",
                        "default": 8000,
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Busca páginas web públicas por una consulta en lenguaje natural y devuelve "
                "una lista corta con título, URL y snippet de cada resultado. Úsala cuando el "
                "usuario pida información de internet sin proporcionar un enlace, o cuando "
                "necesites descubrir fuentes antes de abrirlas con `fetch_webpage`. No devuelve "
                "HTML crudo. Si la búsqueda falla, dilo con claridad en vez de inventar resultados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto a buscar, en lenguaje natural.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Máximo de resultados a devolver (1-10).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]

WEB_TOOL_NAMES = {"fetch_webpage", "web_search"}

# Códigos que suelen ser bloqueo anti-bot o caída transitoria: vale reintentar
# con navegador real. El resto de 4xx/5xx se tratan como fallo definitivo.
_BLOCK_STATUS = {401, 403, 429, 451, 500, 502, 503, 520, 521, 522, 523, 525, 526, 530}


class _TextExtractor(HTMLParser):
    """Convierte HTML en texto plano legible.

    Descarta script/style/etc, captura <title>, y mete saltos de línea en los
    límites de bloque para que el texto no quede todo pegado.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.meta_description: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "meta" and self.meta_description is None:
            attr = dict(attrs)
            name = (attr.get("name") or attr.get("property") or "").lower()
            if name in {"description", "og:description"} and attr.get("content"):
                self.meta_description = attr["content"].strip()
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # <br/>, <meta .../> y similares auto-cerrados.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
            return
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
            return
        if self._skip_depth > 0:
            return
        if data.strip():
            self._chunks.append(data)
        elif data and self._chunks and not self._chunks[-1].endswith((" ", "\n")):
            # Espacio entre tokens inline (ej "<b>hola</b> mundo").
            self._chunks.append(" ")

    @property
    def title(self) -> str:
        return _collapse_inline("".join(self.title_parts))

    @property
    def text(self) -> str:
        raw = "".join(self._chunks)
        # Colapsa espacios horizontales y limita saltos de línea consecutivos.
        lines = [_collapse_inline(line) for line in raw.split("\n")]
        out: list[str] = []
        blank = 0
        for line in lines:
            if line:
                out.append(line)
                blank = 0
            else:
                blank += 1
                if blank <= 1:
                    out.append("")
        return "\n".join(out).strip()


def _collapse_inline(text: str) -> str:
    return re.sub(r"[ \t ​]+", " ", text).strip()


def html_to_text(html: str) -> tuple[str, str, str | None]:
    """Devuelve (title, text, meta_description) a partir de HTML."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # HTML muy roto: fallback a strip de tags por regex.
        stripped = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        stripped = re.sub(r"(?s)<[^>]+>", " ", stripped)
        return "", _collapse_inline(stripped), None
    return parser.title, parser.text, parser.meta_description


# ---------------------------------------------------------------------------
# Cuota de búsqueda (in-memory, rolling-hour)
# ---------------------------------------------------------------------------


class WebSearchQuota:
    """Cuota rolling-hour por usuario, en memoria.

    Estructura: `dict[user_id, deque[float]]` con timestamps en segundos de un
    reloj inyectable (default `time.monotonic`). Se poda la cola izquierda en
    cada `check_and_consume` para mantener la operación O(1) amortizada.

    Convenciones de retorno:
      - `(True, remaining_after_consume)` cuando se permite la búsqueda.
      - `(False, retry_after_seconds)` cuando se deniega; el retry es
        `ceil(events[0] + window_seconds - now)` y siempre `> 0` si la
        denegación viene del cap (los timestamps viejos ya se podaron).
    """

    def __init__(
        self,
        *,
        window_seconds: int = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check_and_consume(self, user_id: str, max_per_hour: int) -> tuple[bool, int]:
        now = self._clock()
        events = self._events[user_id]
        cutoff = now - self.window_seconds
        # Poda inclusiva en el borde: si events[0] <= cutoff, ya expiró.
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= max_per_hour:
            retry = int(ceil(events[0] + self.window_seconds - now))
            return False, max(1, retry)
        events.append(now)
        return True, max(0, max_per_hour - len(events))


# Instancia de módulo (una sola por proceso). Tests inyectan su propio `quota`.
_SEARCH_QUOTA = WebSearchQuota()


# ---------------------------------------------------------------------------
# Parser de DuckDuckGo Lite
# ---------------------------------------------------------------------------


_SNIPPET_MAX_CHARS = 500


def _decode_ddg_redirect(href: str | None) -> str | None:
    """Decodifica el wrapper `https://duckduckgo.com/l/?uddg=<URL>&rut=...` o su
    forma relativa `/l/?uddg=...` a la URL real. Devuelve `None` para hrefs
    vacíos, schemes no soportados o wrappers malformados.
    """
    if not href:
        return None
    href = href.strip()
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlsplit(href)
    if parsed.scheme in {"http", "https"}:
        netloc = parsed.netloc.lower()
        # Forma absoluta del wrapper de DDG.
        if netloc.endswith("duckduckgo.com") and parsed.path == "/l/":
            uddg = (parse_qs(parsed.query).get("uddg") or [None])[0]
            return unquote(uddg) if uddg else None
        # Enlace directo http(s) (DDG a veces lo emite así).
        return href
    # Forma relativa /l/?uddg=... (común en lite.duckduckgo.com).
    # Unificamos ambos casos (/l/ y l/) para evitar urlsplit malformado (kilo review).
    if href.startswith("/l/") or href.startswith("l/"):
        path_q = href if href.startswith("/") else "/" + href
        uddg = (parse_qs(urlsplit(path_q).query).get("uddg") or [None])[0]
        return unquote(uddg) if uddg else None
    return None


class _DDGLiteParser(HTMLParser):
    """Parser streaming del SERP de `lite.duckduckgo.com`.

    Estrategia: rastrear los enlaces con clase `result-link` y los snippets con
    clase `result-snippet`. Esta aproximación es robusta a si los resultados
    se anidan en tablas individuales (como en el fixture de tests) o si están
    dentro de una única tabla mayor (como en la respuesta real actual).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._title_open = False
        self._title_href: str | None = None
        self._title_parts: list[str] = []
        self._snippet_open = False
        self._snippet_parts: list[str] = []
        self.results: list[dict[str, str]] = []
        self._in_result_link_td = False
        self._in_sponsored_table = False  # salta filas patrocinadas

    def _class_tokens(self, raw: str | None) -> set[str]:
        return set((raw or "").lower().split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "td":
            tokens = self._class_tokens(attr.get("class"))
            if "result-link" in tokens:
                self._in_result_link_td = True
            elif "result-snippet" in tokens:
                self._snippet_open = True
                self._snippet_parts = []
        elif tag == "table":
            tokens = self._class_tokens(attr.get("class"))
            if "sponsored" in tokens:
                self._in_sponsored_table = True
        elif tag == "a":
            if self._in_sponsored_table:
                self._title_open = False
                self._title_href = None
                return
            tokens = self._class_tokens(attr.get("class"))
            if "result-link" in tokens or self._in_result_link_td:
                # Si había un resultado pendiente sin snippet finalizado, lo cerramos.
                self._finalize_current()
                self._title_open = True
                self._title_href = attr.get("href")
                self._title_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self._in_sponsored_table = False
        elif tag == "td":
            self._in_result_link_td = False
            if self._snippet_open:
                self._snippet_open = False
                self._finalize_current()
        elif tag == "a" and self._title_open:
            self._title_open = False

    def handle_data(self, data: str) -> None:
        if self._title_open:
            self._title_parts.append(data)
        elif self._snippet_open:
            self._snippet_parts.append(data)

    def _finalize_current(self) -> None:
        if not self._title_href:
            return
        title = _collapse_inline("".join(self._title_parts))
        if not title:
            self._title_href = None
            return
        snippet = _collapse_inline("".join(self._snippet_parts))[:_SNIPPET_MAX_CHARS]
        self.results.append(
            {"title": title, "href": self._title_href, "snippet": snippet}
        )
        self._title_href = None
        self._title_parts = []
        self._snippet_parts = []


def _parse_ddg_lite(html: str) -> list[dict[str, str]]:
    """Extrae una lista de `{title, url, snippet}` del SERP de DDG Lite.

    Decodifica automáticamente el wrapper `duckduckgo.com/l/?uddg=...` y la
    forma relativa `/l/?uddg=...`. Ignora filas `sponsored` y enlaces internos
    del propio buscador. Nunca propaga excepciones: cualquier fallo de parseo
    se traduce en lista vacía.
    """
    if not html:
        return []
    parser = _DDGLiteParser()
    try:
        parser.feed(html)
        parser.close()
        parser._finalize_current()  # kilo: flush último resultado pendiente sin snippet
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for raw in parser.results:
        url = _decode_ddg_redirect(raw.get("href"))
        if not url:
            continue
        # Filtro final defensivo: nunca devolver wrappers ni schemes no http(s).
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if "duckduckgo.com" in parsed.netloc.lower():
            continue
        title = raw["title"]
        snippet = raw.get("snippet", "")
        # Filtro explícito de sponsored (kilo review): evitar que resultados
        # promocionados pasen como búsqueda orgánica.
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        if any(kw in title_lower for kw in ("sponsored", "patrocinado")):
            continue
        if any(kw in snippet_lower for kw in ("sponsored", "patrocinado")):
            continue
        out.append({"title": title, "url": url, "snippet": snippet})
    return out


# ---------------------------------------------------------------------------
# Búsqueda web (DuckDuckGo Lite keyless)
# ---------------------------------------------------------------------------


_DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"


async def web_search(
    query: str,
    *,
    max_results: int = 5,
    safe: bool = True,
    timeout: float = 20.0,
    user_id: str | None = None,
    max_per_hour: int = 10,
    quota: WebSearchQuota | None = None,
    client: httpx.AsyncClient | None = None,
    browser_fallback: bool = False,  # noqa: ARG001 — reservado, no usado en PR 1
) -> dict[str, Any]:
    """Busca en DuckDuckGo Lite (keyless) y devuelve resultados estructurados.

    Nunca propaga excepciones: cualquier fallo (red, parseo, status, timeout,
    cuota agotada, falta de `user_id`) se convierte en `{"error": "..."}` para
    que el tool-loop pueda continuar. El parámetro `browser_fallback` queda
    reservado para una iteración futura (Playwright contra DDG) y se ignora en
    este slice.

    Orden de los chequeos (importa para el contrato de cuota antes de red):
      1. `query` vacío/whitespace → error.
      2. `user_id` ausente → fail-closed, sin construir cliente HTTP.
      3. Cuota rolling-hour → si agotada, error en español y sin request.
      4. HTTP GET a DDG Lite con `q` + `kp` (admin-only) + headers de navegador.
      5. Status `403/429/5xx` o timeouts → error dict.
      6. Parseo vía `_parse_ddg_lite`; payload acotado a `max_results`.
    """
    query_clean = (query or "").strip()
    if not query_clean:
        return {"error": "Falta el texto a buscar (query)."}
    if not user_id:
        return {
            "error": "No se pudo identificar al usuario para aplicar el límite de búsquedas."
        }

    quota_obj = quota or _SEARCH_QUOTA
    allowed, _remaining = quota_obj.check_and_consume(str(user_id), int(max_per_hour))
    if not allowed:
        return {
            "error": "Límite de búsquedas alcanzado. Intenta más tarde."
        }

    max_results = max(1, min(10, int(max_results or 5)))
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=timeout)
    try:
        try:
            response = await client.get(
                _DDG_LITE_URL,
                params={"q": query_clean, "kp": "1" if safe else "-1"},
                headers=_BROWSER_HEADERS,
            )
        except httpx.TimeoutException:
            return {"error": "La búsqueda tardó demasiado (timeout). Intenta de nuevo."}
        except httpx.HTTPError as exc:
            return {"error": f"Fallo de red al buscar: {type(exc).__name__}."}

        status = response.status_code
        if status in {403, 429} or status >= 500:
            return {
                "error": f"El servicio de búsqueda no está disponible (HTTP {status})."
            }
        if status >= 400:
            return {"error": f"La búsqueda falló (HTTP {status})."}

        try:
            html = response.text
        except Exception as exc:
            return {"error": f"No se pudo leer la respuesta de búsqueda: {type(exc).__name__}."}

        try:
            parsed = _parse_ddg_lite(html)
        except Exception as exc:
            return {"error": f"No se pudo interpretar la respuesta de búsqueda: {type(exc).__name__}."}

        bounded = parsed[:max_results]
        return {
            "query": query_clean,
            "safe": bool(safe),
            "results": bounded,
            "count": len(bounded),
            "source": "duckduckgo_lite",
            "fetched_with": "http",
        }
    except Exception as exc:  # última red de seguridad: nunca tumbar el loop
        return {"error": f"Fallo inesperado al buscar: {type(exc).__name__}: {exc}"}
    finally:
        if owns_client and client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Validación SSRF
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url  # asume https si el usuario no puso esquema
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        return None
    if not parts.hostname:
        return None
    return urlunsplit(parts)


def _ip_is_blocked(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _resolve_safe(host: str) -> tuple[bool, str]:
    """Resuelve el host y verifica que ninguna IP apunte a red interna.

    Devuelve (ok, motivo). Si el host es directamente una IP, la valida sin DNS.
    """
    try:
        ipaddress.ip_address(host)
        return (not _ip_is_blocked(host), "IP interna no permitida")
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, f"No se pudo resolver el host «{host}»."
    for info in infos:
        ip = info[4][0]
        if _ip_is_blocked(ip):
            return False, "El destino apunta a una red interna; bloqueado por seguridad."
    return True, ""


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

_JS_SHELL_RE = re.compile(r"enable\s+JavaScript|requires\s+JavaScript|habilita\w*\s+JavaScript", re.IGNORECASE)


def _looks_empty(text: str) -> bool:
    """Heurística: un render por JS deja casi nada de texto útil.

    - Muy poco texto (< 80) → casi seguro un shell sin renderizar.
    - Un poco más, pero con el clásico aviso "enable JavaScript" y aún corto
      (< 400) → también es un shell que necesita navegador.
    Páginas legítimamente breves (ej example.com ≈ 130 chars) pasan sin gastar
    un Chromium.
    """
    stripped = text.strip()
    if len(stripped) < 80:
        return True
    if len(stripped) < 400 and _JS_SHELL_RE.search(stripped):
        return True
    return False


def _build_result(url: str, final_url: str, title: str, text: str, meta: str | None,
                  max_chars: int, source: str, status: int | None) -> dict[str, Any]:
    truncated = len(text) > max_chars
    body = text[:max_chars]
    if not body.strip():
        body = (meta or "").strip()
    return {
        "url": url,
        "final_url": final_url,
        "status": status,
        "title": title or None,
        "description": meta,
        "content": body,
        "length": len(text),
        "truncated": truncated,
        "fetched_with": source,
        "note": "Contenido recortado al límite." if truncated else None,
    }


class _BlockedRedirect(Exception):
    """Un salto de redirección apuntó a un destino no permitido (SSRF)."""


async def _validate_host(host: str) -> tuple[bool, str]:
    return await asyncio.to_thread(_resolve_safe, host)


async def _get_following_redirects(
    client: httpx.AsyncClient, url: str, *, max_redirects: int = 5
) -> tuple[httpx.Response, str]:
    """GET siguiendo redirecciones MANUALMENTE, re-validando cada salto contra SSRF.

    httpx con follow_redirects=True seguiría un Location hacia una IP interna sin
    chequear. Acá deshabilitamos el auto-follow y validamos el host de cada destino
    antes de ir. Lanza _BlockedRedirect si algún salto apunta a red interna.
    """
    current = url
    for _ in range(max_redirects + 1):
        resp = await client.get(current, headers=_BROWSER_HEADERS, follow_redirects=False)
        if not resp.is_redirect:
            return resp, current
        location = resp.headers.get("location")
        if not location:
            return resp, current
        nxt = _normalize_url(urljoin(current, location))
        if nxt is None:
            raise _BlockedRedirect("La redirección apunta a un esquema no permitido.")
        host = urlsplit(nxt).hostname or ""
        ok, reason = await _validate_host(host)
        if not ok:
            raise _BlockedRedirect(reason or "Redirección a red interna bloqueada.")
        current = nxt
    raise _BlockedRedirect("Demasiadas redirecciones.")


async def fetch_webpage(
    url: str,
    *,
    max_chars: int = 8000,
    timeout: float = 20.0,
    client: httpx.AsyncClient | None = None,
    browser_fallback: bool = True,
) -> dict[str, Any]:
    """Descarga una página y devuelve su contenido legible. Nunca lanza: errores
    se devuelven como {"error": ...} para que el tool-loop siga vivo."""
    max_chars = max(1000, min(20000, int(max_chars or 8000)))
    normalized = _normalize_url(url)
    if normalized is None:
        return {"error": "URL inválida. Usa una dirección http/https completa."}
    host = urlsplit(normalized).hostname or ""
    ok, reason = await _validate_host(host)
    if not ok:
        return {"error": reason}

    owns = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
    http_error: str | None = None
    try:
        try:
            resp, final_url = await _get_following_redirects(client, normalized)
            ctype = resp.headers.get("content-type", "").lower()
            status = resp.status_code
            if status < 400 and ("html" in ctype or "xml" in ctype or not ctype):
                title, text, meta = html_to_text(resp.text)
                if not _looks_empty(text) or not browser_fallback:
                    return _build_result(normalized, final_url, title, text, meta, max_chars, "http", status)
                http_error = "Contenido vacío (posible render por JavaScript)."
            elif status < 400 and ("json" in ctype or "text/plain" in ctype or "text/" in ctype):
                # Respuesta no-HTML legible: la devolvemos cruda recortada.
                raw = resp.text
                return _build_result(normalized, final_url, "", raw, None, max_chars, "http", status)
            elif status in _BLOCK_STATUS:
                # 403/429/503/... suelen ser protección anti-bot: un navegador real
                # a veces sí pasa. Vale la pena reintentar con Chromium.
                http_error = f"El servidor respondió {status} (posible bloqueo a clientes simples)."
            elif status >= 400:
                # 404/410/500 definitivos: un navegador devolvería el mismo error.
                # No gastamos un Chromium ni hacemos pasar la página de error por contenido.
                return {
                    "error": f"El servidor respondió {status}. La página no está disponible.",
                    "status": status,
                    "url": normalized,
                    "final_url": final_url,
                }
            else:
                http_error = f"Tipo de contenido no legible ({ctype or 'desconocido'})."
        except _BlockedRedirect as exc:
            # Terminal: NO caemos al navegador, porque Chromium seguiría el mismo
            # redirect hacia la red interna. Cortamos acá.
            return {"error": f"Bloqueado por seguridad: {exc}"}
        except httpx.HTTPError as exc:
            http_error = f"Fallo HTTP directo: {type(exc).__name__}."

        if browser_fallback:
            browser_result = await _fetch_with_browser(normalized, max_chars, timeout)
            if "error" not in browser_result:
                return browser_result
            return {"error": f"{http_error or ''} {browser_result['error']}".strip()}
        return {"error": http_error or "No se pudo obtener la página."}
    finally:
        if owns:
            await client.aclose()


async def _block_internal_route(route: Any) -> None:
    """Handler de Playwright: aborta requests hacia IPs internas (SSRF).

    Best-effort sobre IP literal en el host; los hostnames públicos siguen su
    curso normal (la validación DNS fuerte vive en el path httpx).
    """
    try:
        host = urlsplit(route.request.url).hostname or ""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            await route.continue_()
            return
        if _ip_is_blocked(host):
            await route.abort()
        else:
            await route.continue_()
    except Exception:
        try:
            await route.continue_()
        except Exception:
            pass


async def _fetch_with_browser(url: str, max_chars: int, timeout: float) -> dict[str, Any]:
    """Render con Chromium headless para páginas que dependen de JavaScript o
    bloquean clientes HTTP simples."""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return {"error": "Playwright no está disponible para renderizar la página."}
    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent=_DEFAULT_UA,
            locale="es-ES",
        )
        # Defensa en profundidad SSRF: aunque el host inicial ya se validó, el
        # servidor podría redirigir el navegador a una IP interna. Abortamos
        # cualquier request cuyo host sea una IP literal de red interna.
        await context.route("**/*", _block_internal_route)
        page = await context.new_page()
        try:
            ms = int(timeout * 1000)
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=min(ms, 8000))
            except Exception:
                pass  # networkidle es best-effort; seguimos con lo cargado
            html = await page.content()
            final_url = page.url
            status = resp.status if resp is not None else None
            title, text, meta = html_to_text(html)
            if status is not None and status >= 400:
                return {"error": f"El servidor respondió {status} incluso con navegador."}
            if not text.strip():
                return {"error": "La página no devolvió texto legible ni con navegador."}
            return _build_result(url, final_url, title, text, meta, max_chars, "browser", status)
        finally:
            await context.close()
    except Exception as exc:
        return {"error": f"Fallo al renderizar con navegador: {type(exc).__name__}: {exc}"}
    finally:
        try:
            if browser is not None:
                await browser.close()
        finally:
            if pw is not None:
                await pw.stop()


async def dispatch_web_tool(
    name: str,
    args: dict[str, Any],
    *,
    timeout: float = 20.0,
    user_id: str | None = None,
    search_enabled: bool = True,
    search_safe: bool = True,
    search_max_per_hour: int = 10,
) -> dict[str, Any]:
    """Despacha una tool web por nombre. Aislada de las tools de Discord.

    Nunca propaga excepciones: como DiscordTools.dispatch, devuelve {"error": ...}
    para no tumbar el tool-loop ante un fallo inesperado.

    `search_enabled` actúa como kill switch de defensa en profundidad: aunque el
    schema de la tool quede visible, una llamada `web_search` con la búsqueda
    deshabilitada se rechaza con error y nunca toca la red.
    """
    try:
        if name == "fetch_webpage":
            return await fetch_webpage(
                str(args.get("url") or ""),
                max_chars=int(args.get("max_chars") or 8000),
                timeout=timeout,
            )
        if name == "web_search":
            if not search_enabled:
                return {"error": "La búsqueda web está deshabilitada por configuración."}
            try:
                max_results = int(args.get("max_results") or 5)
            except (TypeError, ValueError):
                max_results = 5
            return await web_search(
                str(args.get("query") or ""),
                max_results=max_results,
                safe=search_safe,
                timeout=timeout,
                user_id=user_id,
                max_per_hour=search_max_per_hour,
            )
        return {"error": f"Tool web desconocida: {name}"}
    except Exception as exc:  # nunca tumbar el loop por una tool
        return {"error": f"Falló la tool web: {type(exc).__name__}: {exc}"}
