import os
import rdflib
import logging
import yaml

logger = logging.getLogger(__name__)

IDENTIFIER_KEY = "identifier"
RDF_FILES_KEY = "ontology_files"
NAMESPACES_KEY = "namespaces"
ACTIVE_REL_KEY = "active_relationships"
DEFAULT_REL_KEY = "default_rel"
ALL_KEYS = set([
    RDF_FILES_KEY, NAMESPACES_KEY, ACTIVE_REL_KEY, DEFAULT_REL_KEY,
    IDENTIFIER_KEY
])

ACTIVE_REL_IRI = rdflib.URIRef("http://osp-core.com/default_rel")  # TODO move
DEFAULT_REL_IRI = rdflib.URIRef("http://osp-core.com/cuba/ActiveRelationship")


class Parser():
    def __init__(self, graph):
        self.graph = graph

    def parse(self, *file_paths):
        """Parse the given YAML files

        Args:
            file_paths (str): path to the YAML file
        """
        for file_path in file_paths:
            with open(file_path, 'r') as f:
                yaml_doc = yaml.safe_load(f)
                if RDF_FILES_KEY in yaml_doc:
                    self._parse_rdf(**self._parse_yml(yaml_doc, file_path))
        logger.info("Loaded ontology with %s triples" % len(self.graph))

    def _parse_yml(self, yaml_doc, file_path):
        """Parse the owl files specified in the given YAML docs

        Args:
            yaml_doc (dict): Parsed YAML doc that specify
                the ontologies to install
            file_path (str): Location of the corresponding YAML file
        """
        yaml_doc[RDF_FILES_KEY] = [
            os.path.join(os.path.dirname(file_path), x)
            for x in yaml_doc[RDF_FILES_KEY]
        ]
        return yaml_doc

    def _parse_rdf(self, **kwargs):
        """Parse the RDF files specified in the kwargs.

        Args:
            kwargs (dict[str, Any]): The keyword arguments usually specified
                in a yaml file.
        """
        # parse input kwargs
        rdf_files = kwargs[RDF_FILES_KEY]
        namespaces = kwargs[NAMESPACES_KEY]
        active_rels = kwargs.get(ACTIVE_REL_KEY, [])
        default_rel = kwargs.get(DEFAULT_REL_KEY, None)
        other_keys = set(kwargs.keys()) - ALL_KEYS
        if other_keys:
            raise TypeError("Specified unknown keys in YAML file: %s"
                            % other_keys)

        # parse the files
        for file in rdf_files:
            self.graph.parse(file)
        default_rels = dict()
        for namespace, iri in namespaces.items():
            if not (
                iri.endswith("#") or iri.endswith("/")
            ):
                iri += "#"
            logger.debug("Create namespace %s" % namespace)
            self.graph.bind(namespace, rdflib.URIRef(iri))
            default_rels[iri] = default_rel

        self._add_cuba_triples(active_rels)
        self._add_default_rel_triples(default_rels)

    def _add_default_rel_triples(self, default_rels):
        for namespace, default_rel in default_rels.items():
            if default_rel is None:
                continue
            self.graph.add((
                rdflib.URIRef(namespace),
                DEFAULT_REL_IRI,
                rdflib.URIRef(default_rel)
            ))

    def _add_cuba_triples(self, active_rels):
        for rel in active_rels:
            self.graph.add(
                (rdflib.URIRef(rel), rdflib.OWL.subObjectPropertyOf,
                 ACTIVE_REL_IRI)
            )
