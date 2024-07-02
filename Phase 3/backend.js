const neo4j = require('neo4j-driver');
const express = require('express');
var queryOverpass = require("query-overpass")
var path = require('path');

const app = express();
const port = 3000


// ENTER NEO4J DATABASE INFORMATION BELOW
const URI = 'bolt://localhost:7687';
const USER = 'USERNAME';
const PASSWORD = 'YOUR PASSWORD';

app.get('/route/:from/:to', async (req, res) => {

    let from_coords = req.params.from.split(", ");
    let to_coords = req.params.to.split(", ");

    let from_node_id = (await coord_to_node(from_coords[0], from_coords[1], 100));
    let to_node_id = (await coord_to_node(to_coords[0], to_coords[1], 100));

    if (from_node_id == null || to_node_id == null)
    {
        res.status(500).send({ error: "No roads found within a kilometer of the starting or ending point. Please try other points." });
        return;
    }

    from_node_id = from_node_id[0].id.replace('node/','');
    to_node_id = to_node_id[0].id.replace('node/','');

    let response = (await get_path(from_node_id, to_node_id));

    if (response == null)
    {
        res.status(501).send({ error: "Route not found between points. Try different points." });
        return;
    }

    response = response[0];

    let distance = response._fields[3];
    let path = response._fields[5];

    res.send([distance,path]);
})

app.listen(port, () => {
    console.log(`Example app listening on port ${port}`)
})

function point_distance(lat1, lon1, lat2, lon2)
{
    return Math.abs(Math.hypot(lat1 - lat2, lon1 - lon2));
}

async function coord_to_node(lat, lon, radius)
{
    return new Promise(resolve => {
        queryOverpass('node(around:' + String(radius) + ',' + String(lat) + ',' + String(lon) + ');way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|motorway_link|trunk_link|primary_link|secondary_link|motorway_junction)$"](around:' + String(radius) + ',' + String(lat) + ',' + String(lon) + ');node(w)(around:' + String(radius) + ',' + String(lat) + ',' + String(lon) + ');out qt 10;', async (err, geojson) => {
            if (err) {
                console.log(err);
            }
    
            let geo_features = geojson.features;
    
            if (geo_features.length <= 0)
            {
                if(radius >= 1000)
                {
                    resolve(null);
                    return;
                }

                geo_features = await coord_to_node(lat, lon, radius * 2)
            }
    
            if(geo_features != null && geo_features.length > 0)
            {
                let closest_node = geo_features[0];
                let closest_distance = point_distance(lat, lon,closest_node.geometry.coordinates[1],closest_node.geometry.coordinates[0]);

                for(var i = 1; i < geo_features.length; i++)
                {
                    let current_distance = point_distance(lat, lon,geo_features[i].geometry.coordinates[1],geo_features[i].geometry.coordinates[0]);

                    if(current_distance < closest_distance)
                    {
                        closest_node = geo_features[i];
                        closest_distance = current_distance;
                    }
                }
    
                geo_features[0] = closest_node;
            }

            resolve(geo_features);
        });
    });
} 

async function get_path(from, to)
{
    const driver = neo4j.driver(URI, neo4j.auth.basic(USER, PASSWORD))
    let session = driver.session({ database: 'roads' })

    try
    {
        const { records, summary, keys } = await driver.executeQuery(
            'MATCH (source:Vertex {vertexId: $v1}), (target:Vertex {vertexId: $v2})\nCALL gds.shortestPath.dijkstra.stream("myGraph", {\nsourceNode: source,\ntargetNode: target,\nrelationshipWeightProperty: "distance"\n})\nYIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path\nRETURN\nindex,\ngds.util.asNode(sourceNode).vertexId AS sourceNodeName,\ngds.util.asNode(targetNode).vertexId AS targetNodeName,\ntotalCost,\n[nodeId IN nodeIds | gds.util.asNode(nodeId).vertexId] AS nodeNames,\n[nodeId IN nodeIds | ("(" + gds.util.asNode(nodeId).location.x + ", " + gds.util.asNode(nodeId).location.y) + ")"] AS Coordinates',
            {v1: from,v2: to},
            { database: 'roads' }
        )

        session.close();
        driver.close();

        return records;
    }
    catch (err)
    {
        return null;
    }
}

app.use(express.static(path.join(__dirname, 'public')));