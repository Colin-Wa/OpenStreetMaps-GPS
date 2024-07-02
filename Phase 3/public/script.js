var map = L.map('map').setView([42.223762, -71.553093], 9);

var point_select = "none";

var startIcon = L.icon({
    iconUrl: 'images/start.png',
    iconSize:     [15, 15]
});
var endIcon = L.icon({
    iconUrl: 'images/end.png',
    iconSize:     [15, 15]
});

var start_marker = null;
var end_marker = null;
var polyline = null;

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

shapecoords = document.getElementById("shapecoords");

map.on("click", function (event) {
    if(point_select == "start")
    {
        if(start_marker == null)
        {
            start_marker = L.marker([event.latlng.lat,event.latlng.lng], {icon: startIcon}).addTo(map);
        }
        else
        {
            start_marker.setLatLng([event.latlng.lat,event.latlng.lng])
        }
    }
    else if (point_select == "end")
    {
        if(end_marker == null)
        {
            end_marker = L.marker([event.latlng.lat,event.latlng.lng], {icon: endIcon}).addTo(map);
        }
        else
        {
            end_marker.setLatLng([event.latlng.lat,event.latlng.lng])
        }
    }
    point_select = "none";
});

function select_starting()
{
    point_select = "start";
    
    if (polyline != null)
    {
        polyline.removeFrom(map);
        polyline = null;
    }
}

function select_ending()
{
    point_select = "end";

    if (polyline != null)
    {
        polyline.removeFrom(map);
        polyline = null;
    }
}

async function call_api() {
    if(start_marker == null || end_marker == null)
    {
        alert("Please make sure to select a starting and ending point before calculating route");
        return;
    }

    output = await fetch("./route/" + String(start_marker._latlng.lat) + ", " + String(start_marker._latlng.lng) + "/" + String(end_marker._latlng.lat) + ", " + String(end_marker._latlng.lng))
    .then((output) => output.json())

    if(output.error)
    {
        alert(output.error);
        return;
    }

    path = output[1]

    fixed_path = []

    for (i in path)
    {
        let temp = path[i].replace('(','');
        temp = temp.replace(')','');
        temp = temp.split(', ');
        fixed_path[i] = temp;
        fixed_path[i][0] = parseFloat(fixed_path[i][0]);
        fixed_path[i][1] = parseFloat(fixed_path[i][1]);
    }

    polyline = L.polyline(fixed_path, {color: 'red'}).addTo(map);

    map.fitBounds(polyline.getBounds());
}