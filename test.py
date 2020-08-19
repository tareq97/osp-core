from osp.core.session.transport.transport_session_client import \
    TransportSessionClient
from osp.core.namespaces import cuba
from osp.wrappers.sqlite import SqliteSession
import logging
import shutil

logging.getLogger("osp.core.session.transport").setLevel(logging.DEBUG)

DB = "double_test.db"
HOST = "127.0.0.1"
PORT = 13472
URI = f"ws://{HOST}:{PORT}"

with TransportSessionClient(SqliteSession, URI, path=DB) as session:
    wrapper = cuba.Wrapper(session=session)
    e = cuba.Entity()
    c = cuba.File(path='try.txt')
    e.add(c, rel=cuba.activeRelationship)
    wrapper.add(e, rel=cuba.activeRelationship)
    wrapper.session.commit()

with TransportSessionClient(SqliteSession, URI, path=DB, file_destination='try_downloads') as session:
    wrapper = cuba.Wrapper(session=session)
    wrapper.session.load_by_oclass(oclass=cuba.File)

shutil.rmtree("try_downloads")

with TransportSessionClient(SqliteSession, URI, path=DB, file_destination='try_downloads') as session:
    wrapper = cuba.Wrapper(session=session)
    wrapper.session.load_by_oclass(oclass=cuba.File)  # this line fails
