import csv
from pqdict import minpq
from math import cos, asin, sqrt, pi

#note: all stop_id, start_id, end_id etc are str, not int

#dict of stops, key is stop_id(str), value is dict with attributes 'name'(str), 'dur'(int), 'lat'(float), 'lng'(float)
stopDict = {}
#dict of routes between connected stops, key is (stop1_id, stop2_id)(tuple of str), value is dict with attributes 
#'dur'(int), 'svc'(list of str), 'coord'(list of str where str = 'lat'/'lng')
routeDict = {}

nodeDict = {}

#parse data from csv files into stopDict and routeDict
def readData():
    with open("nodedata.csv") as f:
        data = csv.reader(f)
        next(data)
        for node_id, node_name, node_lat, node_lng, node_type, node_neigh in data:
            if node_type == 'Bus Stop':
                node_name = node_name + ' (Bus Stop)'
            node_lat, node_lng =  float(node_lat), float(node_lng)
            curr = {'name':node_name, 'lat': node_lat, 'lng': node_lng, 'type': node_type, 'neighbours': node_neigh.split('/')}
            nodeDict[node_id] = curr

    with open("stopdata.csv") as f:
        data = csv.reader(f)
        next(data)
        for stop_id, stop_name, stop_dur, stop_lat, stop_lng in data:
            stop_dur, stop_lat, stop_lng =  int(stop_dur), float(stop_lat), float(stop_lng)
            curr = {'name':stop_name, 'dur': stop_dur, 'lat': stop_lat, 'lng': stop_lng, 'neighbours':[]}
            stopDict[stop_id] = curr
            nodeDict[stop_id]['dur'] = stop_dur
            nodeDict[stop_id]['bus_neighbours'] = []

    with open("routedata.csv") as f:
        data = csv.reader(f)
        next(data)
        for stop1_name, stop1_id, stop2_name, stop2_id, route_dur, services, route_coord in data:
            route_dur, services, route_coord = int(route_dur), services.split(), route_coord.split()
            stopDict[stop1_id]['neighbours'].append(stop2_id)
            nodeDict[stop1_id]['bus_neighbours'].append(stop2_id)
            curr = {'dur': route_dur, 'svc': services, 'coord': route_coord}
            routeDict[(stop1_id,stop2_id)] = curr


#walking speed taken as 1.4m/s
def distance(lat1, lng1, lat2, lng2):
    p = pi/180
    a = 0.5 - cos((lat2-lat1)*p)/2 + cos(lat1*p) * cos(lat2*p) * (1-cos((lng2-lng1)*p))/2
    return 1000 * 12742 * asin(sqrt(a))

#walking speed taken as 1.4m/s
def walk_time(dist):
    return dist * 1.4

#fn to generate shortest path, giving total path duration and list of stop_id visited in sequence
def dijkstra_bus(start_id, end_id):
    distTo = {}
    parent = {}
    pq = minpq()
    
    for stop in stopDict:
        distTo[stop] = float("inf")
        parent[stop] = None
    distTo[start_id] = 0
    pq.additem(start_id, 0)

    while len(pq) > 0:
        curr_id, curr_dist = pq.popitem()
        if curr_dist == distTo[curr_id]:
            if curr_id == end_id:
                break
            for neigh in stopDict[curr_id]['neighbours']:
                if distTo[neigh] > distTo[curr_id] + routeDict[(curr_id,neigh)]['dur']:
                    distTo[neigh] = distTo[curr_id] + routeDict[(curr_id,neigh)]['dur']
                    parent[neigh] = curr_id
                    try: 
                        pq.additem(neigh, distTo[neigh])
                    except: 
                        pq.updateitem(neigh, distTo[neigh])
    
    totalDur = 0
    path_id = []
    path_id.append(end_id)
    
    curr_id = end_id
    while curr_id != start_id:
        totalDur += routeDict[(parent[curr_id],curr_id)]['dur'] + stopDict[parent[curr_id]]['dur']
        curr_id = parent[curr_id]
        path_id.append(curr_id)

    totalDur -= stopDict[start_id]['dur']
    path_id.reverse()
    bus_path = getBus(path_id, start_id, end_id)
    return path_id, bus_path, totalDur



def dijkstra_walk(start_id, end_id):
    distTo = {}
    parent = {}
    pq = minpq()
    
    for node in nodeDict:
        distTo[node] = float("inf")
        parent[node] = None
    distTo[start_id] = 0
    pq.additem(start_id, 0)

    while len(pq) > 0:
        curr_id, curr_dist = pq.popitem()
        curr_lat, curr_lng = nodeDict[curr_id]['lat'], nodeDict[curr_id]['lng']
        if curr_dist == distTo[curr_id]:
            if curr_id == end_id:
                break
            for neigh in nodeDict[curr_id]['neighbours']:
                neigh_lat, neigh_lng = nodeDict[neigh]['lat'], nodeDict[neigh]['lng']
                dist_apart = walk_time(distance(curr_lat, curr_lng, neigh_lat, neigh_lng))
                if distTo[neigh] > distTo[curr_id] + dist_apart:
                    distTo[neigh] = distTo[curr_id] + dist_apart
                    parent[neigh] = curr_id
                    try: 
                        pq.additem(neigh, distTo[neigh])
                    except: 
                        pq.updateitem(neigh, distTo[neigh])
    
    totalDur = distTo[end_id]
    path_id = []
    path_id.append(end_id)
    
    curr_id = end_id
    while curr_id != start_id:
        curr_id = parent[curr_id]
        path_id.append(curr_id)

    path_id.reverse()
    return path_id, totalDur


#generates bus-taking directions, minimizing bus changes along the path_id generated by dijkstra fn

#returns a list where each element is a segment where the user does not have to change bus 
#(e.g. if user takes 3 seperate buses, there are 3 segments)

#each element is [last stop of segment, [list of buses serving segment], 
#[list of stops visited by segment inc first and last], number of stops to take i.e number of stops visited - 1]

#underlying implementation: multisource dijkstra
def getBus(path_id, start_id, end_id):
    bus_graph = {}
    for i in range(len(path_id) - 1):
        stop1_id, stop2_id = path_id[i], path_id[i + 1]
        for bus in routeDict[(stop1_id, stop2_id)]['svc']:
            bus_graph[stop1_id + ' ' + bus] = [stop2_id]
            for j in range(i + 1, len(path_id)-1):
                if bus in routeDict[(path_id[j], path_id[j+1])]['svc']:
                    bus_graph[stop1_id + ' ' + bus].append(path_id[j+1])

    distTo = {}
    parent = {}
    pq = minpq()
    
    for value in bus_graph:
        if value.split()[0] == start_id:
            pq.additem(value, 0)
    for stop_id in path_id:
        distTo[stop_id] = (float("inf"))
        parent[stop_id] = []
    distTo[start_id] = 0

    while len(pq) > 0:
        curr, curr_dist = pq.popitem()
        if curr_dist == distTo[curr.split()[0]]:
            for neigh in bus_graph[curr]:
                if distTo[neigh] > distTo[curr.split()[0]] + 1:
                    distTo[neigh] = distTo[curr.split()[0]] + 1
                    parent[neigh].append(curr)
                    for value in bus_graph:
                        if value.split()[0] == neigh:
                            pq.additem(value, distTo[neigh])
                elif distTo[neigh] == distTo[curr.split()[0]] + 1:
                    parent[neigh].append(curr)

    bus_path = []
    while end_id != start_id:
        curr_buses = []
        for value in parent[end_id]:
            curr_id = value.split()[0]
            if value.split()[1] not in curr_buses:
                curr_buses.append(value.split()[1])
        bus_path.append([stopDict[end_id]['name'], curr_buses, []])
        end_id = curr_id
    bus_path.reverse()
    i,j = 0,0
    while j < len(path_id) and i < len(bus_path):
        if stopDict[path_id[j]]['name'] != bus_path[i][0]:
            bus_path[i][2].append(stopDict[path_id[j]]['name'])
            j += 1
        else:
            bus_path[i][2].append(stopDict[path_id[j]]['name'])
            i += 1

    for segment in bus_path:
        segment.append(len(segment[2])-1)

    return bus_path

# readData()
# print(buildingNames)
#print(dijkstra_walk('101','600'))
# print(stopDict)
# print(nodeDict)