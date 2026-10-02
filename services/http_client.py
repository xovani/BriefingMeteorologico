"""Small cached JSON transport with bounded request rate and explicit failures."""
from dataclasses import dataclass
import logging
import threading
import time

import requests

from config import API_TIMEOUT_SECONDS, CACHE_TTL_SECONDS, USER_AGENT

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiResult:
    data: object = None
    error: str | None = None
    status: int | None = None


class JsonClient:
    def __init__(self, session=None, ttl=CACHE_TTL_SECONDS, clock=time.monotonic):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.ttl = ttl
        self.clock = clock
        self.cache = {}
        self.lock = threading.Lock()
        self.last_request = 0.0
        self.cooldown_until = 0.0

    def get(self, url: str, params: dict) -> ApiResult:
        key = (url, tuple(sorted((k, str(v)) for k, v in params.items())))
        with self.lock:
            now = self.clock()
            cached = self.cache.get(key)
            if cached and now - cached[0] < self.ttl:
                return cached[1]
            if now < self.cooldown_until:
                return ApiResult(error="Limite de consultas atingido; aguarde antes de tentar novamente.", status=429)
            # Less than 100 requests/minute; also spaces Open-Meteo requests.
            delay = 0.7 - (now - self.last_request)
            if delay > 0:
                time.sleep(delay)
            logger.info("Consulta API %s", url)
            self.last_request = self.clock()
            try:
                response = self.session.get(url, params=params, timeout=API_TIMEOUT_SECONDS)
                self.last_request = self.clock()
                if response.status_code == 204:
                    result = ApiResult(data=[], status=204)
                else:
                    response.raise_for_status()
                    result = ApiResult(data=response.json(), status=response.status_code)
                self.cache[key] = (self.clock(), result)
                return result
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status == 429:
                    retry = number_retry(exc.response.headers.get("Retry-After"))
                    self.cooldown_until = self.clock() + retry
                logger.warning("API indisponível %s: HTTP %s", url, status, exc_info=True)
                return ApiResult(error=f"Serviço indisponível (HTTP {status}).", status=status)
            except (requests.RequestException, ValueError):
                logger.warning("Falha de conexão ou JSON inválido: %s", url, exc_info=True)
                return ApiResult(error="Não foi possível acessar o serviço meteorológico. Verifique sua conexão com a internet.")


def number_retry(value) -> float:
    try:
        return max(60, min(600, float(value)))
    except (ValueError, TypeError):
        return 60
