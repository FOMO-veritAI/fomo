"""Busca fontes públicas e lê páginas informadas pelo publisher."""

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from .config import GOOGLE_FACT_CHECK_API_KEY


USER_AGENT = "TAKTA-FOP/0.1 (local research prototype)"
MAX_BYTES = 1_500_000


@dataclass
class RetrievedSource:
    url: str
    title: str
    domain: str
    text: str
    origin: str


def safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
        return bool(addresses) and all(ipaddress.ip_address(entry[4][0]).is_global for entry in addresses)
    except (socket.gaierror, ValueError):
        return False


async def fetch_page(url: str, origin: str = "web") -> RetrievedSource:
    if not await asyncio.to_thread(safe_public_url, url):
        raise ValueError("URL não é pública ou não pôde ser resolvida.")
    async with httpx.AsyncClient(timeout=12, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get(url)
        if response.is_redirect:
            raise ValueError("Redirecionamentos não são aceitos para fontes fornecidas.")
        response.raise_for_status()
        if len(response.content) > MAX_BYTES:
            raise ValueError("A fonte excede o tamanho permitido.")
        if "text/html" not in response.headers.get("content-type", ""):
            raise ValueError("A fonte precisa ser uma página HTML pública.")
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else urlparse(url).hostname or url
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        element.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))[:40000]
    if len(text) < 80:
        raise ValueError("A página não contém texto suficiente para análise.")
    return RetrievedSource(url=url, title=title[:300], domain=urlparse(url).hostname or "", text=text, origin=origin)


def search_terms(claim: str) -> str:
    words = re.findall(r"[\wÀ-ÿ-]+", claim, re.UNICODE)
    stops = {"de", "da", "do", "dos", "das", "em", "com", "para", "por", "uma", "um", "que", "foi", "será", "vai", "entre", "sobre", "ao", "aos", "as", "os", "se"}
    useful = [word for word in words if len(word) > 2 and word.lower() not in stops]
    return " ".join(useful[:8]) or claim[:90]


async def gdelt_urls(claim: str) -> list[str]:
    params = {"query": search_terms(claim), "mode": "artlist", "format": "json", "maxrecords": "8", "timespan": "3months"}
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params)
        response.raise_for_status()
        data = response.json()
    return [item["url"] for item in data.get("articles", []) if item.get("url")]


async def bing_news_urls(claim: str) -> list[str]:
    async with httpx.AsyncClient(timeout=12, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get("https://www.bing.com/news/search", params={"q": search_terms(claim), "format": "rss", "mkt": "pt-BR"})
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    urls = []
    for item in root.findall("./channel/item")[:8]:
        link = item.findtext("link") or ""
        # O feed usa um link de redirecionamento; a URL da fonte está no parâmetro url.
        actual = parse_qs(urlparse(link).query).get("url", [link])[0]
        if actual.startswith("https://") or actual.startswith("http://"):
            urls.append(actual)
    return urls


async def google_fact_check_urls(claim: str) -> list[str]:
    if not GOOGLE_FACT_CHECK_API_KEY:
        return []
    params = {"query": search_terms(claim), "languageCode": "pt", "pageSize": 5, "key": GOOGLE_FACT_CHECK_API_KEY}
    async with httpx.AsyncClient(timeout=12, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get("https://factchecktools.googleapis.com/v1alpha1/claims:search", params=params)
        response.raise_for_status()
        data = response.json()
    return [review["url"] for claim_item in data.get("claims", []) for review in claim_item.get("claimReview", []) if review.get("url")]


async def search_sources(claim: str) -> tuple[list[RetrievedSource], list[str]]:
    urls: list[tuple[str, str]] = []
    errors: list[str] = []
    for label, finder in (("Bing News", bing_news_urls), ("GDELT", gdelt_urls), ("Google Fact Check", google_fact_check_urls)):
        try:
            urls.extend((url, label) for url in await finder(claim))
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}")
    unique = list(dict.fromkeys(urls))[:10]
    pages = await asyncio.gather(*(fetch_page(url, origin) for url, origin in unique), return_exceptions=True)
    sources = [page for page in pages if isinstance(page, RetrievedSource)]
    if unique and not sources:
        errors.append("Os resultados foram encontrados, mas as páginas não puderam ser lidas.")
    return sources, errors
