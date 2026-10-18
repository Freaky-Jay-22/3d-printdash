"""Fake Bambu FTPS (implicit TLS) for testing the print-preview download.
Bambu printers listen on port 990; binding it needs root (fine in a dev container).
Put a .3mf into dev/ftproot/cache/ to simulate the running job."""
import os
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import TLS_FTPHandler
from pyftpdlib.servers import FTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "ftproot")
os.makedirs(os.path.join(ROOT, "cache"), exist_ok=True)


class Implicit(TLS_FTPHandler):
    def handle(self):
        # implicit TLS: secure the control connection before the banner
        self.secure_connection(self.ssl_context)

    def handle_ssl_established(self):
        TLS_FTPHandler.handle(self)


a = DummyAuthorizer()
a.add_user("bblp", "12345678", ROOT, perm="elradfmw")
Implicit.authorizer = a
Implicit.certfile = os.path.join(HERE, "cert.pem")
Implicit.keyfile = os.path.join(HERE, "key.pem")
Implicit.tls_control_required = True
Implicit.tls_data_required = True
Implicit.passive_ports = range(60000, 60100)
FTPServer(("127.0.0.1", int(os.environ.get("FTPS_PORT", 990))), Implicit).serve_forever()
