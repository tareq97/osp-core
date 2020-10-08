"""This file contains a tool for migrating from old to new database schemas."""

import rdflib
from osp.core.session.db.sql_wrapper_session import SqlWrapperSession
from osp.core.session.db.sql_util import SqlQuery
from osp.core.namespaces import get_entity
from osp.core.utils import iri_from_uid
from osp.core.namespaces import cuba

INT = rdflib.XSD.integer
STR = rdflib.XSD.string

versions = {
    "OSP_MASTER": 0,
    "OSP_V1_CUDS": 1
}


class SqlMigrate():
    """Tool to migrate from old to new database schema."""

    def __init__(self, sql_session: SqlWrapperSession):
        """Initialize the migration tool."""
        self.session = sql_session
        self.tables = sql_session._get_table_names("")
        self.version = min(v for tbl, v in versions.items()
                           if tbl in self.tables)
        self.max_version = max(versions.values())
        self.procedure = SqlMigrate.procedures[self.version][self.max_version]

    def run(self):
        """Run the migration."""
        self.procedure(self)

    def migrate_0_1(self):
        """Migrate from version 0 to 1."""
        self.namespaces = {}
        self.entities = {}
        self.cuds = {}

        self._init_transaction()
        if self.session.root is None:
            cuba.Wrapper(session=self.session)
       try:
            self.migrate_master_0_1()
            self.migrate_relations_0_1()
            self.migrate_data_0_1()
            self.delete_old_tables_0()
            self._commit()
        except Exception as e:
            self._rollback_transaction()
            raise e

    def migrate_master_0_1(self):
        """Migrate the OSP_MASTER table."""
        c = self.session._do_db_select(
            SqlQuery("OSP_MASTER", ["uid", "oclass"],
                     {"uid": "UUID", "oclass": STR})
        )
        for uid, oclass in c:
            oclass = get_entity(oclass) if oclass != "" else cuba.Wrapper
            ns_iri = str(oclass.namespace.get_iri())

            ns_idx = self.get_ns_idx_0_1(ns_iri)
            oclass_idx = self.get_entity_idx_0_1(ns_idx, oclass)
            cuds_idx = self.get_cuds_idx_0_1(uid)

            self.session._do_db_insert(
                "OSP_V1_TYPES", ["s", "o"], [cuds_idx, oclass_idx],
                {"s": INT, "o": INT}
            )

    def migrate_relations_0_1(self):
        """Migrate the relations from v0 to v1."""
        c = self.session._do_db_select(
            SqlQuery("OSP_RELATIONSHIPS", ["origin", "target", "name"],
                     {"origin": "UUID", "target": "UUID", "name": STR})
        )
        for origin, target, name in c:
            rel = get_entity(name)

            ns_idx = self.get_ns_idx_0_1(rel.namespace.get_iri())
            p = self.get_entity_idx_0_1(ns_idx, rel)
            s = self.get_cuds_idx_0_1(origin)
            o = self.get_cuds_idx_0_1(target)

            self.session._do_db_insert(
                "OSP_V1_RELATIONS", ["s", "p", "o"], [s, p, o],
                {"s": INT, "p": INT, "o": INT}
            )

    def migrate_data_0_1(self):
        """Migrate the data from v0 to v1."""
        tables = self.session._get_table_names("CUDS_")
        for table in tables:
            oclass = get_entity(table[5:].replace("___", "."))
            attributes, columns, datatypes = self.get_col_spec_0(oclass)
            self.migrate_data_table_0_1(table, columns, datatypes, attributes)

    def migrate_data_table_0_1(self, table, columns, datatypes, attributes):
        """Migrate a single data table for v0 to v1."""
        c = self.session._do_db_select(SqlQuery(table, columns, datatypes))
        for row in c:
            cuds_idx = self.get_cuds_idx_0_1(row[-1])  # uuid is lasr element
            for col, attr, value in zip(columns, attributes, row):
                datatype = datatypes[col] or STR
                self.migrate_data_triple_0_1(attr, datatype, cuds_idx, value)

    def migrate_data_triple_0_1(self, attr, datatype, cuds_idx, value):
        """Migrate a single data triple from v0 to v1."""
        from osp.core.session.db.sql_util import get_data_table_name
        ns_idx = self.get_ns_idx_0_1(attr.namespace.get_iri())
        attr_idx = self.get_entity_idx_0_1(ns_idx, attr)
        self.session._do_db_insert(
            get_data_table_name(datatype),
            ["s", "p", "o"],
            [cuds_idx, attr_idx, value],
            {"s": INT, "p": INT, "o": datatype}
        )

    def get_cuds_idx_0_1(self, uid):
        """Get CUDS index when migrating from v0 to v1."""
        cuds_iri = str(iri_from_uid(uid))
        if cuds_iri not in self.cuds:
            self.cuds[cuds_iri] = self.session._do_db_insert(
                "OSP_V1_CUDS", ["uid"], [str(uid)], {"uid": "UUID"}
            )
        cuds_idx = self.cuds[cuds_iri]
        return cuds_idx

    def get_ns_idx_0_1(self, ns_iri):
        """Get Namespace index when migrating from v0 to v1."""
        ns_iri = str(ns_iri)
        if ns_iri not in self.namespaces:
            self.namespaces[ns_iri] = self.session._do_db_insert(
                "OSP_V1_NAMESPACES", ["namespace"], [ns_iri],
                {"namespace": STR}
            )
        ns_idx = self.namespaces[ns_iri]
        return ns_idx

    def get_entity_idx_0_1(self, ns_idx, entity):
        """Get entity index when migrating from v0 to v1."""
        entity_iri = str(entity.iri)
        if entity_iri not in self.entities:
            self.entities[entity_iri] = self.session._do_db_insert(
                "OSP_V1_ENTITIES", ["ns_idx", "name"],
                [ns_idx, entity.name], {"ns_idx": INT, "name": STR}
            )
        return self.entities[entity_iri]

    def get_col_spec_0(self, oclass):
        """Get the columns specification of CUDS tables in schema v0."""
        attributes = list(oclass.attributes)
        columns = [x.argname for x in attributes] + ["uid"]
        datatypes = dict(uid="UUID", **{x.argname: x.datatype
                                        for x in attributes})
        return attributes, columns, datatypes

    def delete_old_tables_0(self):
        for table in self.tables:
            self.session._drop_table(table)

    def no_migration(self):
        """Do nothing."""

    procedures = {
        0: {
            0: no_migration,
            1: migrate_0_1
        }
    }


if __name__ == "__main__":
    from osp.wrappers.sqlite import SqliteSession
    session = SqliteSession("test.db")
    m = SqlMigrate(session)
    m.run()
