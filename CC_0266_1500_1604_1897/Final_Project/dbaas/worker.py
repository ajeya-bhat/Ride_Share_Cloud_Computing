#Required imports

from flask import Flask, render_template, jsonify, request, abort, g,request
from werkzeug.exceptions import BadRequest
from sqlalchemy import create_engine, Sequence
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import String, Integer, Float, Boolean, Column, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from kazoo.client import KazooClient
import pika
import requests
import logging
import random
import csv
import json
import threading
import pika
import sys
import os
import docker


app = Flask(__name__)

#Used for crating Object Relational Mappings of tables in the database
Base = declarative_base()

#Used to connect to the Docker SDK
client1 = docker.APIClient(base_url='unix://var/run/docker.sock')
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

#Connect to the zookepeer Container
zk = KazooClient(hosts='zookeeper:2181')
zk.start()

#Worker znode created
result = "worker"
strmaster="slave,"+str(result)
print("strslave:",strmaster)
strmaster1=bytes(strmaster, 'ascii')
zk.create("/zookeeper/node_worker", strmaster1,ephemeral=True,sequence=True)

#Lists all the container process ids of the workers
def list_pid():
    pid_list = []
    countp=0
    for container in client.containers.list():
        countp+=1
        temp=client1.inspect_container(container.id)['State']['Pid']
        pid_list.append(temp)
    pid_list.sort()
    print("countp",pid_list[countp-1])
    return pid_list[countp-1]

#User schema
class User(Base):
    __tablename__ = 'User'
    username = Column(String(8080), primary_key=True)
    password = Column(String(40))

    def init(self, username, password):
        self.username = username
        self.password = password
#Ride schema
class Ride(Base):
    __tablename__ = 'Ride'
    rideid = Column(Integer, primary_key=True)
    createdby = Column(String(8000), nullable=False)
    source = Column(String(80), nullable=False)
    dest = Column(String(80), nullable=False)
    timestamp = Column(DateTime,nullable=False)

#Riders schema
class Riders(Base):
    __tablename__ = 'Riders'
    rideid = Column(Integer, ForeignKey('Ride.rideid',ondelete = 'CASCADE'),primary_key=True)
    username = Column(String(8000), primary_key = True)

#Create sqlite database file and connect to the database
engine = create_engine('sqlite:///ride_share.db', connect_args={'check_same_thread': False}, echo=True,pool_pre_ping=True)
con = engine.connect()
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session=Session()

#Function to sync the newly created slave with all the writes that are stored in text file
def syncFirst() :
    f = open("/code/queries.txt","r")
    f1  = f.readlines()
    for query in f1 :
        con.execute(query)

#Callback function of the channel sync receive that executes the write requests sent from master
def callbackForSync(ch, method, properties, body):
        body=str(body)
        body=body[2:-1]
        con.execute(body)

#Function that consumes for read and sync messages from RPC and SyncReceive channels respectively
def reader():
    #Channel RPC is the channel for sending data read from the database in slave container to the orchestrator container waiting for response
    channelRPC = connection.channel()
    channelRPC.queue_declare(queue='rpc_queue')
    channelRPC.basic_qos(prefetch_count=30)
    channelRPC.basic_consume(queue='rpc_queue', on_message_callback=on_request,auto_ack=True)
    
    #Channel SyncReceive is the channel for receiving write requests from the master
    channelSyncReceive = connection.channel()
    channelSyncReceive.exchange_declare(exchange='logs', exchange_type='fanout')
    result = channelSyncReceive.queue_declare(queue='sync_queue')
    queue_name = result.method.queue
    channelSyncReceive.queue_bind(exchange='logs', queue="sync_queue")
    channelSyncReceive.basic_consume(
        queue=queue_name, on_message_callback=callbackForSync, auto_ack=True)

    channelSyncReceive.start_consuming()
    channelRPC.start_consuming()

#called by master to publish sync requests to all the slaves
def writeToSyncQueue(str1):
    #Channel sync send is the channel that is used by the master to send the write query to all the slaves
    channelSyncSend = connection.channel()
    channelSyncSend.exchange_declare(exchange='logs', exchange_type='fanout')     
    channelSyncSend.basic_publish(exchange='logs', routing_key="sync_queue", body=str1)
    
#executes the write request in the database
def writetodb(str1):
    str1 = str1[2:-1]
    f = open("/code/queries.txt","a+")
    try:
        con.execute(str1)
        
    except:
        print("Already exists")
    else:
        f.write(str1 + '\n')
        writeToSyncQueue(str1)

#callback function of channel writer
def callback(ch, method, properties, body):
    abc=str(body)
    writetodb(abc)

#executes the read request in the database
#returns the data read as a JSON Response       
def readfromdb(str1):
    str1=str1[2:-1]
    print("reading from",os.environ["container_name"])
    str1 = str1.replace('\\', '')
    user_details=json.loads(str1)
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

#Publishes the data read from database to the RPC Queue
def on_request(ch, method, properties, body):
    n = str(body)
    response = readfromdb(n)
    ch.basic_publish(exchange='',
                     routing_key=properties.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         properties.correlation_id),
                     body=response)

#Consume for write requests sent from Orchestrator
def writer():
    #Channel Writer is used by master to consume write requests sent from the Orchestrator
    channelWriter = connection.channel()
    channelWriter.queue_declare(queue='WRITE_queue',durable=True)
    channelWriter.basic_qos(prefetch_count=30)
    channelWriter.basic_consume(queue='WRITE_queue', on_message_callback=callback,auto_ack=True)
    channelWriter.start_consuming()

#Declaring the connection and channels
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq'))
    
#Based on the environment variable called "container_type" the worker runs as master or slave
if __name__ == '__main__':
    if os.environ["container_type"] == "master" :
        writer()
    else :
        syncFirst()
        reader()
    app.run(host='0.0.0.0',port=8000)

