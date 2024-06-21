import osmium
from neo4j import GraphDatabase, basic_auth
import csv
import os
import wget

BATCH_SIZE = 1000000

class OSM_Data_Container():
    def __init__(self, db_import_file_location):
        self.nodes = []
        self.relationships = []
        self.import_location = db_import_file_location
        self.node_count = 0
        self.relationship_count = 0

        with open(str(self.import_location) + '/nodes.csv','a') as file:
            writer = csv.writer(file)
            writer.writerow(["vertexId:ID{label:Vertex}","location:point{crs:WGS-84}"])
            file.close()

        with open(str(self.import_location) + '/relationships.csv','a') as file:
            writer = csv.writer(file)
            writer.writerow([":START_ID", ":END_ID", ":TYPE"])
            file.close()

    def append_node(self, node):
        # node is assumed to be of the form
        # [ID, LATITUDE, LONGITUDE]

        self.nodes.append(node)

        self.node_count = self.node_count + 1

        if(len(self.nodes) >= BATCH_SIZE):
            self.write_nodes_to_file()

    def append_relationship(self, relationship):
        # relationship is assumed to be of the form
        # [START_NODE_ID, END_NODE_ID]

        self.relationships.append(relationship)
        
        self.relationship_count = self.relationship_count + 1

        if(len(self.relationships) >= BATCH_SIZE):
            self.write_relationships_to_file()

    def write_nodes_to_file(self):
        print("Saving batch of nodes to file... Total Nodes: " + str(self.node_count),end="\r")
        with open(str(self.import_location) + '/nodes.csv','a') as file:
            writer = csv.writer(file)
            for n in self.nodes:
                writer.writerow(n)
            file.close()
        self.nodes = []

    def write_relationships_to_file(self):
        print("Saving batch of relationships to file... Total Relationships: " + str(self.relationship_count),end="\r")
        with open(str(self.import_location) + '/relationships.csv','a') as file:
            writer = csv.writer(file)
            for w in self.relationships:
                writer.writerow(w)
            file.close()
        self.relationships = []

class Neo4j_Interface():
    def __init__(self, url, username, password, db_import_file_location):
        self.driver = GraphDatabase.driver(url, auth=basic_auth(username, password))
        self.import_location = db_import_file_location

    def import_csvs(self):
        print("Importing CSV files...                                                  ")
        os.system("bin\\neo4j-admin database import incremental --force --skip-duplicate-nodes --nodes=Vertex=import/nodes.csv --relationships=import/relationships.csv roads")
        print("Done")

    def close(self):
        self.driver.close()

    def save_distances(self):
        self.driver.execute_query("""
            CALL apoc.periodic.iterate(
            "MATCH (v1:Vertex)-[:IS_BEFORE]->(v2:Vertex)
            WITH v1,v2
            RETURN v1,v2",
            "MERGE (v1)-[r:IS_BEFORE]->(v2)
            SET r.distance = point.distance(v1.location, v2.location)", 
            {batchSize:1000})
        """,
        database_="roads"
        )

    def remove_disconnected_nodes(self):
        self.driver.execute_query("""
            CALL apoc.periodic.iterate(
            "MATCH (v1:Vertex)
            WHERE NOT (v1)--()
            RETURN v1",
            "DELETE (v1)",
            {batchSize:1000})
        """,
        database_="roads"
        )

class WayIterator(osmium.SimpleHandler):
    def __init__(self, odc):
        super(WayIterator, self).__init__()
        self.types_of_highway = ["motorway","trunk","primary","secondary","tertiary","unclassified","residential","service","motorway_link","trunk_link","primary_link","secondary_link","motorway_junction"]
        self.odc = odc
    def node(self, n):
        node_loc = str(n.location).split("/")
        latitude = float(node_loc[0])
        longitude = float(node_loc[1])
        self.odc.append_node([n.id, "{latitude:" + str(latitude) + ", longitude:" + str(longitude) + "}"])

    def way(self, w):
        if w.tags.get('highway') in self.types_of_highway:
            for j in range(0,len(w.nodes)):
                if j - 1 >= 0 and ((not 'oneway' in w.tags.__dict__.keys()) or w.tags['oneway'] == "no"):
                    self.odc.append_relationship([w.nodes[j],w.nodes[j - 1],"IS_BEFORE"])
                if j + 1 < len(w.nodes):
                    self.odc.append_relationship([w.nodes[j],w.nodes[j + 1],"IS_BEFORE"])

def download_file(url, output_path):
    print("Downloading OSM file at " + str(url))
    output_path = wget.download(url, output_path)
    print("\nDone")
    return output_path

def main():
    
    DATABASE_PATH = "INPUT THE FILE LOCATION OF YOUR DATABASE"

    # File URL for OSM Data
    download_file("LINK TO OSM FILE DOWNLOAD", "Phase 2/osm-file.osm.pbf")

    odc = OSM_Data_Container(str(DATABASE_PATH) + "/import")

    wi = WayIterator(odc)
    wi.apply_file("Phase 2/osm-file.osm.pbf")

    odc.write_nodes_to_file()
    odc.write_relationships_to_file()

    # Database must be OFF prior to importing
    # ALSO a constraint must be created to tell the database what a Vertex is
    # If the database is already existing, this should not be an issue, but if
    # the database was just created use the following in the database's cypher input:

    # CREATE CONSTRAINT vertexId
    # FOR (vertex:Vertex) REQUIRE vertex.vertexId IS UNIQUE

    # Make sure the database is off
    input("Make sure the database is not running, then enter any character to continue: ")

    # If an error occurs when importing data, restart the database, turn it off again, then rerun the code

    ni = Neo4j_Interface("bolt://localhost:INPUT THE PORT YOUR SERVER IS ON", "neo4j", "INPUT YOUR DATABASE PASSWORD", str(DATABASE_PATH) + "/import")

    os.chdir(DATABASE_PATH)

    ni.import_csvs(DATABASE_PATH)

    # Have the user tart the database

    input("Start the database, and enter any character to continue: ")

    ni.remove_disconnected_nodes()

    ni.save_distances()

    ni.close()


main()