from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
import json

import requests
from rdflib import Graph
from SPARQLWrapper import SPARQLWrapper, JSON, POST, GET
from pandas import DataFrame


class FusekiConfig:
    def __init__(self,
                 host: str = "fuseki",
                 port: int = 3030,
                 dataset: str = "sample-dataset",
                 user: Optional[str] = "admin",
                 password: Optional[str] = "admin"):
        self.host = host
        self.port = port
        self.dataset = dataset
        self.user = user
        self.password = password
        self.base_url = f"http://{host}:{port}"


class FusekiClient:
    def __init__(self, config: FusekiConfig = FusekiConfig()):
        self.config = config
        self.__create_dataset_if_not_exists()

    def __create_dataset_if_not_exists(self) -> bool:
        datasets_url = f"{self.config.base_url}/$/datasets"
        sparql = SPARQLWrapper(datasets_url)
        sparql.setReturnFormat(JSON)
        if self.config.user and self.config.password:
            sparql.setHTTPAuth('BASIC')
            sparql.setCredentials(self.config.user, self.config.password)

        try:
            results = sparql.query().convert()
            datasets = [dataset['ds.name'][1:] for dataset in results['datasets']]

            if self.config.dataset in datasets:
                print(f"Dataset '{self.config.dataset}' already exists.")
                return True

            # If dataset doesn't exist, create it
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            data = {'dbName': self.config.dataset, 'dbType': 'tdb2'}

            auth = (self.config.user, self.config.password) if self.config.user and self.config.password else None
            response = requests.post(datasets_url, headers=headers, data=data, auth=auth)

            if response.status_code == 200:
                print(f"Dataset '{self.config.dataset}' created successfully.")
                return True
            else:
                print(f"Failed to create dataset. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return False

    def clear_dataset(self) -> None:
        with FusekiQueryExecutor(self.config, "DELETE WHERE { ?s ?p ?o }") as executor:
            executor.execute()

    def setup_example_graph(self) -> FusekiClient:
        client = FusekiClient(self.config)
        client.clear_dataset()
        example_data = """
        @prefix : <http://example.org/> .
        @prefix foaf: <http://xmlns.com/foaf/0.1/> .

        :alice foaf:name "Alice" ;
               foaf:knows :bob .

        :bob foaf:name "Bob" ;
             foaf:knows :charlie .

        :charlie foaf:name "Charlie" ;
                 foaf:knows :alice .
        """
        client.load_turtle_data(example_data)

    def sparql(self, query: str) -> FusekiQueryExecutor:
        return FusekiQueryExecutor(self.config, query)

    def load_turtle_file(self, file_path: str) -> None:
        print(f"Loading ttl file: {file_path}")
        with open(file_path, 'r') as file:
            turtle_data = file.read()
        self.load_turtle_data(turtle_data)
        print("Turtle file loaded successfully.")

    def load_turtle_data(self, turtle_data: str) -> None:
        print("Loading ttl data...")
        g = Graph()
        g.parse(data=turtle_data, format="turtle")
        insert_query = "INSERT DATA { " + " ".join(f"{s.n3()} {p.n3()} {o.n3()} ." for s, p, o in g) + " }"
        with FusekiQueryExecutor(self.config, insert_query) as executor:
            executor.execute()
        print("Turtle data loaded successfully.")


class FusekiQueryExecutor:
    def __init__(self, config: FusekiConfig, query: str):
        self.config = config
        self.query = query
        self.sparql = None

    def __enter__(self) -> FusekiQueryExecutor:
        self.sparql = SPARQLWrapper(f"{self.config.base_url}/{self.config.dataset}")
        if self.config.user and self.config.password:
            self.sparql.setHTTPAuth('BASIC')
            self.sparql.setCredentials(self.config.user, self.config.password)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sparql = None

    def execute(self) -> None:
        if not self.sparql:
            raise ValueError("SPARQLWrapper is not initialized. Use with statement.")
        self.sparql.setMethod(POST)
        self.sparql.setQuery(self.query)
        self.sparql.query()

    def execute_as_json(self) -> Dict[str, Any]:
        if not self.sparql:
            raise ValueError("SPARQLWrapper is not initialized. Use with statement.")
        self.sparql.setReturnFormat(JSON)
        self.sparql.setMethod(GET)
        self.sparql.setQuery(self.query)
        results = self.sparql.query().convert()
        return results

    def execute_as_df(self) -> DataFrame:
        rows = []
        for binding in self.execute_as_json()["results"]["bindings"]:
            row = {}
            for var, data in binding.items():
                row[f"{var}"] = data['value']
                row[f"{var}_type"] = data['type']
            rows.append(row)

        return DataFrame(rows)


if __name__ == '__main__':
    FusekiClient(FusekiConfig(host="localhost")).setup_example_graph()
    client = FusekiClient(FusekiConfig(host="localhost", dataset="bookstore"))
    client.load_turtle_file("./ttls/bookstore.ttl")
    with client.sparql("""
    PREFIX : <http://example.org/bookstore/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?book ?title
    WHERE {
      ?book rdf:type :Book ;
            :title ?title .
    }
    """) as q:
        result = q.execute_as_df()

