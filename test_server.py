from osp.wrappers.sqlite import SqliteSession
from osp.core.session.transport.transport_session_server import \
    TransportSessionServer
import logging

logging.getLogger("osp.core.session.transport").setLevel(logging.DEBUG)

HOST = "127.0.0.1"
PORT = 13472
SERVER_DIR = "server_dir"

server = TransportSessionServer(SqliteSession, HOST, PORT,
                                file_destination=SERVER_DIR)
print("ready", flush=True)
server.startListening()
