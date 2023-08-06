#Required imports

from flask import Flask, render_template, jsonify, request, abort, g,request
from werkzeug.exceptions import BadRequest
from datetime import datetime
from multiprocessing import Value
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

#Utility unction to increase the count of the requests. Requests are increased with the help of a lock for tackling concurrency issues.
def http_count():
    with counter.get_lock():
        counter.value += 1
        
#Health Check to confirm Load balancer is sending requests to Rides Instance
@app.route('/',methods=["GET"])
def dummy_api():
    return {},200

#API for adding a user into the User table. 
#Returns an empty JSON array, and the HTTP response status code.
@app.route('/api/v1/users', methods=["PUT","POST"])
def adduser():
    http_count()
    if request.method == "POST" :
        return {},405
    user = dict(request.json)
    pwd = user["password"]
    user['table']='User'
    user['where']='username='+ "'" + user['username']+ "'"
    user['columns']='username'
    results=requests.post('http://<database-instance-ip>/api/v1/db/read', json = user).json()
    user['isPut'] = 1
    user['table'] = 'User'
    user['insert'] = '"' + user['username'] + '"' + ',' + '"' + user['password'] + '"'
    count = 0
    for row in results :
        count += 1
    if count == 0:
        if sha(pwd) == False :
            return {},400
        res = requests.post('http://<database-instance-ip>/api/v1/db/write', json = user)
        return {},201
    elif count>0:
        return {},400
    else:
        return {},405

#API for removing a user from the User table. 
#Returns an empty JSON array, and the HTTP response status code.
@app.route('/api/v1/users/<username>', methods=["DELETE"])
def removeuser(username):
    http_count()
    if(username == ""):
        return {},400
    userForRead={}
    userForRead['table']='User'
    userForRead['columns']='username'
    userForRead['where']='username'+ '=' + "'"  + username+"'"
    results=requests.post('http://<database-instance-ip>/api/v1/db/read',json=userForRead).json()
    count = 0
    for _ in results :
        count += 1
    if count == 0:
        return {},400
    elif count>0:
        d={}
        d['table'] = 'User'
        d['value']=username
        d['isPut']=0
        d['column']= 'username'
        requests.post('http://<database-instance-ip>/api/v1/db/write', json = d)
        d['isPut'] = 0
        d['table'] = 'Ride'
        d['column']= 'createdby'
        requests.post('http://<database-instance-ip>/api/v1/db/write', json = d)
        d['isPut'] = 0
        d['table'] = 'Riders'
        d['column']= 'username'
        requests.post('http://<database-instance-ip>/api/v1/db/write', json = d)
        return {},200
    else:
        return {},405
    
#API for getting all users from the User table. 
#Returns a JSONified list of all the users of Users table, and the HTTP response status code.
@app.route('/api/v1/users', methods=["GET"])
def listallusers():
    http_count()
    print(request,request.headers.get('Origin'))
    ride = {}
    l=[]
    ride['table']='User'
    ride['where']='1=1'
    ride['columns']='username'
    res_ride = requests.post('http://<database-instance-ip>/api/v1/db/read', json = ride).json()
    for i in res_ride:
        l1=i.values()
        l.extend(l1)
    if len(l)==0:
        return json.dumps(l),204
    return json.dumps(l),200

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

#main function to run the server. Server runs on the port 8000, and host as 0.0.0.0
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=8000)
