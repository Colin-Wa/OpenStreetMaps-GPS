import overpy
import numpy as np
from queue import PriorityQueue
import geopy.distance
import folium
from geopy.geocoders import Nominatim

class List_of_Nodes:
    def __init__(self, api, center, radius):
        self.nodes = {}

        print("Searching routes within " + str(radius) + " meters of the midpoint")

        # Query OSM Overpass api for all ways within a radius of a given point

        self.osm_data = api.query('way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|motorway_link|trunk_link|primary_link|secondary_link|motorway_junction)$"](around:' + str(radius) + ',' + str(center[0]) + ', ' + str(center[1]) + ');(._;>;); out body;')

        for i in self.osm_data.nodes:
            self.add_node(Node(i))

        # Create relationships between nodes, if a street is one way, ignore the node behind it

        for i in self.osm_data.ways:
            for j in range(0,len(i.nodes)):

                if j - 1 >= 0 and ((not 'oneway' in i.tags.keys()) or i.tags['oneway'] == "no"):
                    self.nodes[i.nodes[j].id].neighbors.append(i.nodes[j - 1].id)
                if j + 1 < len(i.nodes):
                    self.nodes[i.nodes[j].id].neighbors.append(i.nodes[j + 1].id)

    def add_node(self, node):
        self.nodes[node.id] = node

    def print(self):
        for i in list(self.nodes.values()):
            i.print()

    # Calculate shortest path between two OSM nodes - Using Djikstra's algorithm
    # with geographic distance between nodes as distance heuristic

    def navigate(self, source, destination):
        for i in list(self.nodes.values()):
            i.distance = np.infty

        source.distance = 0
        visited = set()
        queue = PriorityQueue()
        queue.put((0,source))

        current = source

        while queue.empty() == False:
            current = queue.get()[1]

            if current in visited:
                continue

            visited.add(current)

            for neighbor in self.nodes[current.id].neighbors:
                tentative_distance = current.distance + geopy.distance.geodesic((current.lat, current.lon),(self.nodes[neighbor].lat, self.nodes[neighbor].lon)).mi

                neighbor_distance = self.nodes[neighbor].distance
                if tentative_distance < neighbor_distance:
                    self.nodes[neighbor].distance = tentative_distance
                    self.nodes[neighbor].predecessor = current

                    queue.put((self.nodes[neighbor].distance, self.nodes[neighbor]))

        current = destination

        route = []

        while current != None:
            route.append(current.id)
            current = current.predecessor

        return route
    
    def get_line_from_route(self, route):
        line = []
        for i in route:
            line.append((self.nodes[i].lat,self.nodes[i].lon))
        return line
            

class Node:
    def __init__(self, node_object):
        self.id = node_object.id
        self.lat = node_object.lat
        self.lon = node_object.lon
        self.neighbors = []
        self.distance = np.infty
        self.predecessor = None


    def print(self):
        print(str(self.id) + ": " + str(self.distance))

class Geos:
    def __init__(self, source_address, dest_address):
        self.source_address = source_address
        self.dest_address = dest_address
        self.geolocator = Nominatim(user_agent="djikstra_gps")
        start_location = self.geolocator.geocode(source_address)
        end_location = self.geolocator.geocode(dest_address)
        self.start_coords = (start_location.raw['lat'], start_location.raw['lon'])
        self.end_coords = (end_location.raw['lat'], end_location.raw['lon'])
        self.center_coords = ((float(self.start_coords[0]) + float(self.end_coords[0])) / 2,(float(self.start_coords[1]) + float(self.end_coords[1])) / 2)
        self.radius = int(geopy.distance.geodesic(self.start_coords, self.center_coords).m) + 300

    def get_osm_node(self, osm_api, order):
        if order == 0:
            location = self.start_coords
            address = self.source_address
        else:
            location = self.end_coords
            address = self.dest_address

        point = {'nodes': []}
        radius = 15
        start_loop = True

        while(start_loop or len(point.nodes) <= 0):
            print("Searching for roads within " + str(radius) + " meters of " + str(address))
            point = osm_api.query('way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|motorway_link|trunk_link|primary_link|secondary_link|motorway_junction)$"](around: ' + str(radius) + ',' + str(location[0]) + ", " + str(location[1]) + ');(._;>;); out qt;')
            radius = radius + 5
            start_loop = False

        # Sort streets by distance and pick the closest one

        closest_distance = np.infty
        closest_point = None
        for i in point.nodes:
            cur_distance = geopy.distance.geodesic((i.lat, i.lon),(location[0],location[1]))
            if cur_distance < closest_distance:
                closest_distance = cur_distance
                closest_point = i
        return closest_point.id

def main():

    # Get User Location Input

    start_loc = input("Enter Starting Address: ")
    end_loc = input("Enter Destination Address: ")

    api = overpy.Overpass()

    for_geo = Geos(start_loc, end_loc)
    
    # Convert the starting and ending locations to OSM nodes

    start_node = for_geo.get_osm_node(api, 0)
    end_node = for_geo.get_osm_node(api, 1)

    radius = for_geo.radius

    nodes = List_of_Nodes(api, for_geo.center_coords, radius)

    # Calculate the route from the start node to the end node

    route = nodes.navigate(nodes.nodes[start_node],nodes.nodes[end_node])

    # If A route cannot be calculated, try using a larger radius (Assuming the route
    # is possible, and just not in scope)

    while len(route) <= 1:
        radius = radius + 200
        nodes = List_of_Nodes(api, for_geo.center_coords, radius)
        route = nodes.navigate(nodes.nodes[start_node],nodes.nodes[end_node])

    # Place the calculated route on a map and save it to an html file

    m = folium.Map(location=(for_geo.center_coords), zoom_start=15)

    folium.PolyLine(nodes.get_line_from_route(route)).add_to(m)

    m.save("index.html")

main()