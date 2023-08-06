#Required imports

from flask import Flask, render_template, jsonify, request, abort, g
import requests
from werkzeug.exceptions import BadRequest
from sqlalchemy import create_engine, Sequence
from sqlalchemy import String, Integer, Float, Boolean, Column, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import random
import csv
import json

app = Flask(__name__)

dict1 = dict()
comma = ','
quotes = '"'

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

Base = declarative_base()

#User Schema
class User(Base):
    __tablename__ = 'User'
    username = Column(String(8000), primary_key=True)
    password = Column(String(40))

    def __init__(self, username, password):
        self.username = username
        self.password = password

#Rides Schema
class Ride(Base):
    __tablename__ = 'Ride'
    rideid = Column(Integer, primary_key=True)
    createdby = Column(String(8000),ForeignKey('User.username',ondelete = 'CASCADE'), nullable=False)
    source = Column(String(80), nullable=False)
    dest = Column(String(80), nullable=False)
    timestamp = Column(DateTime,nullable=False)

#Riders Schema
class Riders(Base):
    __tablename__ = 'Riders'
    rideid = Column(Integer, ForeignKey('Ride.rideid',ondelete = 'CASCADE'),primary_key=True)
    username = Column(String(8000), ForeignKey('User.username',ondelete = 'CASCADE'), primary_key = True)
        
engine = create_engine('sqlite:///sqllight.db', connect_args={'check_same_thread': False}, echo=True,pool_pre_ping=True)
con = engine.connect()
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session=Session()

#Checks if the password provided meets the constraints
def sha(password) :
    hexa_decimal = ['1','2','3','4','5','6','7','8','9','0','a','b','c','d','e','f','A','B','C','D','E','F']
    if len(password) == 40 :
        for i in password :
            if i not in hexa_decimal :
                return False
        return True
    return False

#API for adding a user into the User table. 
#Returns an empty JSON array, and the HTTP response status code. 
@app.route('/api/v1/users', methods=["PUT"])
def adduser():
    user = dict(request.json)
    pwd = user['password']
    user['table']='User'
    user['where']='username='+ "'" + user['username']+ "'"
    user['columns']='username'
    results=requests.post('http://localhost:5000/api/v1/db/read', json = user).json()
    user['isPut'] = 1
    user['table'] = 'User'
    user['insert'] = '"' + user['username'] + '"' + ',' + '"' + user['password'] + '"'
    count = 0
    for row in results :
        count += 1
    if count == 0:
        if sha(pwd) == False :
            return {},400
        res = requests.post('http://localhost:5000/api/v1/db/write', json = user)
        return {},201
    elif count>0:
        return {},400
    else:
        return {},405
    
#API for removing a user from the User table. 
#Returns an empty JSON array, and the HTTP response status code. 
@app.route('/api/v1/users/<username>', methods=["DELETE"])
def removeuser(username):
    if(username == ""):
        return {},400
    userForRead={}
    userForRead['table']='User'
    userForRead['columns']='username'
    userForRead['where']='username'+ '=' + "'"  + username+"'"
    results=requests.post('http://localhost:5000/api/v1/db/read',json=userForRead).json()
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
        requests.post('http://localhost:5000/api/v1/db/write', json = d)
        d['isPut'] = 0
        d['table'] = 'Ride'
        d['column']= 'createdby'
        requests.post('http://localhost:5000/api/v1/db/write', json = d)
        d['isPut'] = 0
        d['table'] = 'Riders'
        d['column']= 'username'
        requests.post('http://localhost:5000/api/v1/db/write', json = d)
        return {},200
    else:
        return {},405


#API for creating a new ride in the Ride and Riders table. 
#Returns an empty JSON array, and the HTTP response status code. 
@app.route('/api/v1/rides', methods=["POST"])
def createride():
    ride = dict(request.json)
    count = 0
    if 'source' not in ride.keys() or 'destination' not in ride.keys() or 'created_by' not in ride.keys() or 'timestamp' not in ride.keys() :
        return {},400
    date = parse(ride['timestamp'])
    d = datetime(date[0],date[1],date[2],date[3],date[4],date[5])
    if d < datetime.now() :
        return {},400
    ride['table']='User'
    ride['where']='username='+"'"+ride['created_by']+"'"
    ride['columns']='username'
    results=requests.post('http://localhost:5000/api/v1/db/read', json = ride).json()
    for row in results :
        count += 1
    if count == 1:
        if str(ride['source']) in dict1.keys() and str(ride['destination']) in dict1.keys():
            ride_id=0
            ride['table']='Ride'
            ride['where']="1=1"
            ride['columns']='rideid'
            res=requests.post('http://localhost:5000/api/v1/db/read', json = ride).json()
            print(res)
            ride_count = 0
            for row in res :
                ride_count += 1
            if ride_count >= 1 :
                for row in res :
                    if ride_id<row['rideid']:
                        ride_id = row['rideid']   
                print(ride_id)                 
                ride_id += 1
            else :
                ride_id = 1
            print(ride_id)
            ride['isPut'] = 1
            ride['table'] = 'Ride'
            ride['insert'] = str(ride_id) + comma + quotes + ride['created_by'] + quotes + comma + str(ride['source']) + comma + str(ride['destination']) + comma + quotes + ride['timestamp'] + quotes
            res = requests.post('http://localhost:5000/api/v1/db/write', json = ride)
            ride['isPut'] = 1
            ride['table'] = 'Riders'
            ride['insert'] = str(ride_id) + comma + quotes + ride['created_by'] + quotes
            print(ride_id)
            print("create"+ride['timestamp'])
            res = requests.post('http://localhost:5000/api/v1/db/write', json = ride)
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
    source = request.args.get('source')
    print("Source:" + source)
    destination = request.args.get('destination')
    if source == None or destination == None or source == '' or destination == '':
        return {},400
    try:
        if int(source) not in range(1,199) or int(destination) not in range(1,199) :
            return {},400
    except:
        return {},400
    res = {}
    res['columns'] = 'rideid,createdby,source,dest,timestamp'
    res['table'] = 'Ride'
    res['where'] = 'source = ' + source + ' and dest = ' + destination
    res = requests.post('http://localhost:5000/api/v1/db/read', json = res)
    res = res.json()
    l = []
    print("entry")
    for row in res :
        print('here')
        date = parse(row['timestamp'])
        print(date)
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
    try:
        if int(rideId):
            pass
    except:
        return {},400
    ride = {}
    ride['table']='Ride'
    ride['where']='rideid='+rideId
    ride['columns']='createdby,timestamp,source,dest'
    res_ride=requests.post('http://localhost:5000/api/v1/db/read', json = ride).json()
    response = {}
    response['rideId'] = rideId
    count = 0
    for row in res_ride :
        count += 1
    if count == 0 :
        return {},204
    elif count>0:
        res_ride = requests.post('http://localhost:5000/api/v1/db/read', json = ride).json()
        ride['columns']='username'
        ride['table']='Riders'
        res_rider = requests.post('http://localhost:5000/api/v1/db/read', json = ride).json()
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
    user = dict(request.json)
    user['table']='User'
    user['where']='username='+"'"+user['username']+"'"
    user['column']='username'
    results=requests.post('http://localhost:5000/api/v1/db/read', json = user)
    count = 0
    for i in results :
        count += 1
    if count == 0 :
        return {},400
    user['table']='Ride'
    user['where']='rideid='+rideId
    user['column']='rideid,timestamp'
    res= requests.post('http://localhost:5000/api/v1/db/read', json = user)
    count = 0
    ride = {}
    for _ in res :
        count += 1
    if count == 0 :
        return {},400
    else :
        ride['table'] = 'Riders'
        ride['insert'] = rideId + comma + quotes + user["username"] + quotes
        ride['isPut'] = 1
        res = requests.post('http://localhost:5000/api/v1/db/write', json = ride)
        return {},200
            
#API for deleting a ride from the Rides and Riders table given the ride ID.
#Returns an empty JSON array , and the HTTP response status code.
@app.route('/api/v1/rides/<rideId>', methods=["DELETE"])
def deleteride(rideId):
    ride = {}
    ride['table']='Ride'
    ride['where']='rideid='+rideId
    ride['columns']='createdby,timestamp,source,dest'
    res= requests.post('http://localhost:5000/api/v1/db/read', json = ride).json()
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
        res = requests.post('http://localhost:5000/api/v1/db/write', json = ride)
        ride['table'] = 'Ride'
        
        res = requests.post('http://localhost:5000/api/v1/db/write', json = ride)
        return {},200

#API for updating the required table. The update could be inserting a row or removing a row.
#Returns the stringified cursor object of the executed query
@app.route('/api/v1/db/write', methods=["POST"])
def writetodb():
    user_details = request.json
    if user_details['isPut']==1:
        rs = con.execute('INSERT INTO ' + user_details['table'] + ' VALUES(' + user_details['insert'] + ')')
        return str(rs)
    else:
        rs=con.execute('DELETE FROM ' + user_details['table'] + ' WHERE  ' + user_details['column'] + '=' '"' + user_details['value'] + '"')
        return str(rs)

#API for reading from the required table. 
#Returns the JSONified list of the details of the read query executed.
@app.route('/api/v1/db/read', methods=["POST"])
def readfromdb():
    user_details = dict(request.json)
    rs = con.execute('SELECT '+ user_details['columns'] + ' FROM ' + user_details['table'] + ' WHERE ' + user_details['where'])
    list1=[]
    for row in rs:
        d={}
        l=user_details['columns'].split(',')
        if len(row):
            for colNo in range(0,len(row)):
                d[l[colNo]]=row[colNo]
            list1.append(d)
    return json.dumps(list1)

#main function to run the server
if __name__ == '__main__':
    app.run(debug=True)
