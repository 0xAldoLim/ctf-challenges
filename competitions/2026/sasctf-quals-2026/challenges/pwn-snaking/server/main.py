import argparse
import signal
from collections import namedtuple
from urllib.parse import unquote, urlsplit

import jnius_config

jnius_config.add_options(
    '-Djava.security.manager',
    '-Djava.security.policy==restrict.policy',
    '-Djava.security.properties=jnius.security',
    '-Xbootclasspath/a:/usr/local/lib/python3.12/dist-packages/jnius/src',
    '-Xmx256m'
)

from jnius import PythonJavaClass, autoclass, java_method

signal.signal(signal.SIGSEGV, signal.SIG_DFL)

class Java:
    Proxy = autoclass("java.net.Proxy")
    ProxyType = autoclass("java.net.Proxy$Type")
    InetSocketAddress = autoclass("java.net.InetSocketAddress")
    HttpClient = autoclass("requester.HttpClient")
    RequestBuilder = autoclass("requester.Request$Builder")


class ProxyAuthenticator(PythonJavaClass):
    __javainterfaces__ = ['requester.ProxyAuthenticator']

    @classmethod
    def from_creds(cls, username: str | None = None, password: str | None = None) -> 'ProxyAuthenticator':
        self = cls.__new__(cls)
        self._username = username
        self._password = password
        return self

    @java_method('(Lrequester/Request;)V')
    def authenticate(self, request) -> None:
        print("todo...")


Proxy = namedtuple('Proxy', ['schema', 'hostname', 'port', 'username', 'password'])


def parse_proxy(value: str) -> Proxy:
    parsed_proxy = urlsplit(value)
    if parsed_proxy.scheme not in ('http', 'https'):
        raise ValueError("Only http:// and https:// schemas are supported now")
    if not parsed_proxy.hostname:
        raise ValueError("Proxy URL must include a hostname")
    if parsed_proxy.username and not parsed_proxy.password:
        raise ValueError("Proxy URL includes username but no password")
    if parsed_proxy.password and not parsed_proxy.username:
        raise ValueError("Proxy URL includes password but no username")
    return Proxy(
        schema=parsed_proxy.scheme,
        hostname=parsed_proxy.hostname,
        port=parsed_proxy.port or {"http": 80, "https": 443}[parsed_proxy.scheme],
        username=unquote(parsed_proxy.username) if parsed_proxy.username else None,
        password=unquote(parsed_proxy.password) if parsed_proxy.password else None,
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='General Java HTTP client wrapper')
    parser.add_argument('--url', type=str, required=True, help='URL to send the request to')
    parser.add_argument('--proxy', type=parse_proxy, help='Proxy server in the URI format')
    return parser.parse_args()


def gift():
    """ Should've brute-forced 12 bits, but I'm feeling nice today :P """
    with open("/proc/self/maps", "r") as f:
        for line in f:
            if "libc.so.6" in line:
                print("Gift:", f'0x{line.split("-")[0]}')
                break


def main() -> None:
    args = parse_args()
    gift()

    client_builder = Java.HttpClient().newBuilder()
    if args.proxy is not None:
        client_builder.proxy(Java.Proxy(
            Java.ProxyType.HTTP,
            Java.InetSocketAddress(args.proxy.hostname, args.proxy.port)
        ))

        if args.proxy.username is not None and args.proxy.password is not None:
            client_builder.proxyAuthenticator(
                ProxyAuthenticator.from_creds(args.proxy.username, args.proxy.password)
            )

    client = client_builder.build()
    req = Java.RequestBuilder().url(args.url).build()

    try:
        resp = client.newCall(req).execute()
        print("Response code:", str(resp.code()))
        print("Response body:", str(resp.body())[:0x200])
        resp.close()
    
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == '__main__':
    main()
