"""Truy cập web công khai: robots.txt, timeout và khoảng nghỉ tối thiểu 3 giây."""
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests


class PublicFetcher:
    """Kiểm tra robots trên từng đích chuyển hướng; lỗi kiểm tra thì không tải."""

    def __init__(self, user_agent, delay=3.0, session=None):
        self.user_agent = user_agent
        self.delay = max(3.0, delay)
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.robots = {}
        self.last_request = None

    def wait(self):
        """Giữ khoảng cách giữa các request, kể cả robots và retry."""
        if self.last_request is not None:
            pause = self.delay - (time.monotonic() - self.last_request)
            if pause > 0:
                time.sleep(pause)
        self.last_request = time.monotonic()

    def _request(self, url, **kwargs):
        self.wait()
        return self.session.get(url, allow_redirects=False, **kwargs)

    def allowed(self, url):
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
                return False
        except ValueError:
            return False
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self.robots:
            parser = RobotFileParser(host + "/robots.txt")
            try:
                response = self._request(parser.url, timeout=30)
                if response.status_code in (404, 410):
                    parser.parse([])  # máy chủ xác nhận không có robots.txt
                elif response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser = None
            except requests.RequestException:
                parser = None
            self.robots[host] = parser
        parser = self.robots[host]
        return parser is not None and parser.can_fetch(self.user_agent, url)

    def get(self, url, **kwargs):
        """Tải tài nguyên sau kiểm tra robots; không vượt chuyển hướng bị chặn."""
        for _ in range(11):
            if not self.allowed(url):
                raise PermissionError(f"robots.txt không cho phép hoặc chưa kiểm tra được: {url}")
            response = self._request(url, **kwargs)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise requests.RequestException("Chuyển hướng thiếu Location")
            url = urljoin(url, location)
        raise requests.TooManyRedirects("Quá nhiều chuyển hướng")
