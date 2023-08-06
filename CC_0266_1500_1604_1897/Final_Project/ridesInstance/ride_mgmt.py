#Required imports

from flask import Flask, render_template, jsonify, request, abort, g
from datetime import datetime
from multiprocessing import Value
from werkzeug.exceptions import BadRequest
import requests
import random
import csv
import json

app = Flask(__name__)

dict1 = dict()
comma = ','
quotes = '"'
counter = Value('i', 0)

#Parses the whole datetime string into year, month, days, hours, minutes and seconds.
#Returns the tuple of year, month, days, hours, minutes and seconds.
def parse(datetime) :
    
    date,time = datetime.split(':')
    dd,momo,yy = date.split('-')
    ss,mm,hh = time.split('-')
    
    return (int(yy),int(momo),int(dd),int(hh),int(mm),int(ss))

#Open the csv file and store each row as a dictionary with key as Place and value as area code
with open('AreaNameEnum.csv') as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    line_count = 0
    for row in csv_reader:
        dict1[row[0]] = row[1]

#Checks if the password provided meets the constraints
def sha(password) :
    hexa_decimal = ['1','2','3','4','5','6','7','8','9','0','a','b','c','d','e','f','A','B','C','D','E','F']
    if len(password) == 40 :
        for i in password :
            if i not in hexa_decimal :
                return False
        return True
    return False

#Health Check to confirm Load balancer is sending requests to Rides Instance
@app.route('/',methods=["GET"])
def dummy_api():
    return  {},200

#Utility unction to increase the count of the requests. Requests are increased with the help of a lock for tackling concurrency issues.
def http_count():
    with counter.get_lock():
        counter.value += 1

#API for adding a user into the User table. 
#Returns a JSONified list of a single number having the number of requests sent to the rides instance, and the HTTP response status code.
@app.route('/api/v1/_count',methods=["GET"])
def http_count1():
    list1 = []
    list1.append(counter.value)
    return json.dumps(list1),200

#API for resetting the counts sent to the rides instance. 
#Returns an empty JSON array, and the HTTP response status code.
@app.route('/api/v1/_count',methods=["DELETE"])
def http_count_reset():
    with counter.get_lock():
        counter.value = 0
    return {},200

#API for counting the number of rides in the Ride table of the rides instance. 
#Returns a JSONified list of a single number having the number of rides in the Ride table, and the HTTP response status code.
@app.route('/api/v1/rides/count',methods=["GET"])
def ride_count():
     http_count()
     list1 = []
     ride = {}
     ride['table']='Ride'
     ride['where']="1=1"
     ride['columns']='rideid'
     res=requests.post('http://<database-instance-ip>/api/v1/db/read', json = ride).json()
     ride_count = 0
     for row in res :
         ride_count += 1
     list1.append(ride_count)
     return json.dumps(list1),200

#API for creating a new ride in the Ride and Riders table. 
#Returns an empty JSON array, and the HTTP response status code.
@app.route('/api/v1/rides', methods=["POST","PUT"])
def createride():
    http_count()
    if request.method == "PUT" :
        return {},405
    ride = dict(request.json)
    count = 0
    if 'source' not in ride.keys() or 'destination' not in ride.keys() or 'created_by' not in ride.keys() or 'timestamp' not in ride.keys() :
        return {},400
    date = parse(ride['timestamp'])
    d = datetime(date[0],date[1],date[2],date[3],date[4],date[5])
    if d < datetime.now() :
        return {},400
    results=requests.get('http://ajeyaexponential-982805114.us-east-1.elb.amazonaws.com/api/v1/users',headers = {'Origin':'<ip address of rides>'})
    for _ in results:
        count+=1
    if count==0:
        return {},400
    results=results.json()
    
    
    l=results
    a=ride['created_by']
    
    count=0
    if a in l:
        count=1
    if count == 1:
        if str(ride['source']) in dict1.keys() and str(ride['destination']) in dict1.keys():
            ride_id=0
            ride['table']='Ride'
            ride['where']="1=1"
            ride['columns']='rideid'
            res=requests.post('http://<database-instance-ip>/api/v1/db/read', json = ride).json()
            ride_count = 0
            for row in res :
                ride_count += 1
            if ride_count >= 1 :
                for row in res :
                    if ride_id<row['rideid']:
                        ride_id = row['rideid']
                ride_id += 1
            else :
                ride_id = 1
            ride['isPut'] = 1
            ride['table'] = 'Ride'
            ride['insert'] = str(ride_id) + comma + quotes + ride['created_by'] + quotes + comma + str(ride['source']) + comma + str(ride['destination']) + comma + quotes + ride['timestamp'] + quotes
            res = requests.post('http://<database-instance-ip>/api/v1/db/write', json = ride)
            ride['isPut'] = 1
            ride['table'] = 'Riders'
            ride['insert'] = str(ride_id) + comma + quotes + ride['created_by'] + quotes
            res = requests.post('http://<database-instance-ip>/api/v1/db/write', json = ride)
            return {},201
        else :
            return {},400
    elif count!=1:
        return {},400
    else :
        return {},405

#API for listing the upcoming rides for the given source and destination from the Rides table. 
#Returns a JSON array of the list of upcoming rides for the given source and destination, and the HTTP response status code.
@app.route('/api/v1/rides', methods=["GET"])
def listupcomingride():
    http_count()
    source = request.args.get('source')
    destination = request.args.get('destination')
    res = {}
    res['columns'] = 'rideid,createdby,source,dest,timestamp'
    res['table'] = 'Ride'
    res['where'] = 'source = ' + source + ' and dest = ' + destination
    res = requests.post('http://<database-instance-ip>/api/v1/db/read', json = res)
    res = res.json()
    if source == None or destination == None or source == '' or destination == '':
        return {},400
    try:
        if int(source) not in range(1,199) or int(destination) not in range(1,199) :
            return {},400
    except:
        return {},400
    l = []
    for row in res :
        date = parse(row['timestamp'])
        d = datetime(date[0],date[1],date[2],date[3],date[4],date[5])
        if d > datetime.now() :
            l.append({'rideId' : row['rideid'],'username' : row['createdby'],'timestamp' : row['timestamp']})
        
    if l == [] :
        return {},204

    return jsonify(l),200

#API for listing the details of the given ride ID from the Rides and Riders table. 
#Returns a JSON array of the list of the details of the given ride ID, and the HTTP response status code.
@app.route('/api/v1/rides/<rideId>', methods=["GET"])
def listride(rideId):
    http_count()
    try:
        if int(rideId):
            pass
    except:
        return {},400
    ride = {}
    ride['table']='Ride'
    ride['where']='rideid='+rideId
    ride['columns']='createdby,timestamp,source,dest'
    res_ride=requests.post('http://<database-instance-ip>/api/v1/db/read', json = ride).json()
    response = {}
    response['rideId'] = rideId
    
    count = 0
    for row in res_ride :
        count += 1
    if count == 0 :
        return {},204
    elif count>0:
        res_ride = requests.post('http://<database-instance-ip>/api/v1/db/read', json = ride).json()
        ride['columns']='username'
        ride['table']='Riders'
        res_rider = requests.post('http://<database-instance-ip>/api/v1/db/read', json = ride).json()
        for row in res_ride :
            response["createdby"] = row['createdby']
            response["timestamp"] = row['timestamp']
            response["source"] = row['source']
            response["destination"] = row['dest']
            
        response["users"] = []
        for row in res_rider :
            response["users"].append(row['username'])
        return response,200
    else:
        return {},405

#API for a user joining a ride given ride ID in the URL, and the user details as part of the body. 
#Returns an empty JSON array, and the HTTP response status code.
@app.route('/api/v1/rides/<rideId>', methods=["POST"])
def joinride(rideId):
    http_count()
    user = dict(request.json)
    print("asa")
    results=requests.get('http://ajeyaexponential-982805114.us-east-1.elb.amazonaws.com/api/v1/users',headers = {'Origin':'<ip address of rides>'})
    first_count = 0
    for _ in results :
        first_count += 1
    print("hdh")
    print(first_count)
    if first_count == 0 :
        return {},400
    results=results.json()
    l=results
    count = 0
    a=user["username"]
    if a in l:
        count=1
    print(results)
    print(count)
    if count == 0 :
        return {},400
    user['table']='Ride'
    user['where']='rideid='+rideId
    user['columns']='rideid,timestamp'
    print("1234")
    res= requests.post('http://<database-instance-ip>/api/v1/db/read', json = user)
    count = 0
    ride = {}
    for _ in res :
        count += 1
    print(count)
    if count == 0 :
        return {},400
    else :
        ride['table'] = 'Riders'
        ride['insert'] = rideId + comma + quotes + user["username"] + quotes
        ride['isPut'] = 1
        res = requests.post('http://<database-instance-ip>/api/v1/db/write', json = ride)
        return {},200

#API for deleting a ride from the Rides and Riders table given the ride ID.
#Returns an empty JSON array , and the HTTP response status code.
@app.route('/api/v1/rides/<rideId>', methods=["DELETE"])
def deleteride(rideId):
    http_count()
    ride = {}
    ride['table']='Ride'
    ride['where']='rideid='+rideId
    ride['columns']='createdby,timestamp,source,dest'
    res= requests.post('http://<database-instance-ip>/api/v1/db/read', json = ride).json()
    count = 0
    ride = {}
    for _ in res :
        count += 1
    if count == 0 :
        return {},400

    else :
        ride['table'] = 'Riders'
        ride['column'] = 'rideid'
        ride['isPut'] = 0
        ride['value']=rideId
        res = requests.post('http://<database-instance-ip>/api/v1/db/write', json = ride)
        ride['table'] = 'Ride'
        res = requests.post('http://<database-instance-ip>/api/v1/db/write', json = ride)
        return {},200
        
#main function to run the server. Server runs on the port 8000, and host as 0.0.0.0
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=8000)

