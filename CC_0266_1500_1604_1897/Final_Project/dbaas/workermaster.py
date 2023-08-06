import pika
from flask import Flask, render_template, jsonify, request, abort, g,request
import requests
import logging
#import sqlite3
#import status
from werkzeug.exceptions import BadRequest
#from models import sessions
app = Flask(__name__)
from sqlalchemy import create_engine, Sequence
from sqlalchemy import String, Integer, Float, Boolean, Column, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker
import random
from datetime import datetime
import csv
import json
import threading
import pika
import sys
import os
import docker
from kazoo.client import KazooClient
pika_logger = logging.getLogger('pika')
pika_logger.level = logging.DEBUG
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
client1 = docker.APIClient(base_url='unix://var/run/docker.sock')
client = docker.DockerClient(base_url='unix://var/run/docker.sock')
flagsync=1
flagread=1
flagwrite=0

def list_pid():
    pid_list = []
    countp=0
    for container in client.containers.list():
    	if "slave" in container.name:
		    countp+=1
		    temp=client1.inspect_container(container.id)['State']['Pid']
		    pid_list.append(temp)
    pid_list.sort()
    print(pid_list)
    print("countp",pid_list[countp-1])
    return pid_list[countp-1]

zk = KazooClient(hosts='zookeeper:2181')
zk.start()
result=0
if os.environ["container_type"] == "master":
	for container in client.containers.list():
		if "master" in container.name:
			result=client1.inspect_container(container.id)['State']['Pid']
			break

	strmaster="master,"+str(result)
elif os.environ["container_type"] == "slave":
	result = list_pid()
	strmaster="slave,"+str(result)
print("strslave:",strmaster)
strmaster1=bytes(strmaster, 'utf-8')
path=zk.create("/zookeeper/node_worker", strmaster1,ephemeral=True,sequence=True)
print("PATH:",path)

class User(Base):
    __tablename__ = 'User'
    username = Column(String(8080), primary_key=True)
    password = Column(String(40))

    def init(self, username, password):
        self.username = username
        self.password = password

class Ride(Base):
    __tablename__ = 'Ride'
    rideid = Column(Integer, primary_key=True)
    createdby = Column(String(8000), nullable=False)
    source = Column(String(80), nullable=False)
    dest = Column(String(80), nullable=False)
    timestamp = Column(DateTime,nullable=False)

class Riders(Base):
    __tablename__ = 'Riders'
    rideid = Column(Integer, ForeignKey('Ride.rideid',ondelete = 'CASCADE'),primary_key=True)
    username = Column(String(8000), primary_key = True)

engine = create_engine('sqlite:///ride_share.db', connect_args={'check_same_thread': False}, echo=True,pool_pre_ping=True)
con = engine.connect()
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session=Session()

def syncFirst() :
    f = open("/code/queries.txt","r")
    print("iam here")
    f1  = f.readlines()
    for query in f1 :
        con.execute(query)
    print("out of syncfirst")

def callbackForSync(ch, method, properties, body):
        print("the body is =",body)
        print("the first chara is =",body[0])
        print("the last chara is =",body[-1])
        print("type = ",type(body))
        body=str(body)
        print("after string",body)
        body=body[2:-1]
        print("after string",body)
        #body=body[1:]
        print("THe slave is recieving =",body)
        con.execute(body)

def reader():   
    
    try:
        result = channelSyncReceive.queue_declare(queue='sync_queue')
        queue_name = result.method.queue
        channelSyncReceive.queue_bind(exchange='logs', queue="sync_queue")
        channelSyncReceive.basic_consume(
        queue=queue_name, on_message_callback=callbackForSync, auto_ack=True)
        print(' [*] Waiting for logs. To exit press CTRL+C')    
        print("am i seen")    
        print(" [x] Awaiting RPC requests")
        #channelSyncReceive.start_consuming()
        channelRPC.start_consuming()
    except:
        print("RPC and SyncR closed") 

def writeToSyncQueue(str1):        
    channelSyncSend.basic_publish(exchange='logs', routing_key="sync_queue", body=str1)
    print(" [x] Sent %r" %str1)

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

    

def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)
    abc=str(body)
    writetodb(abc)
    print(" [x] Done")
       
def readfromdb(str1):
    print("i was here")
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


def on_request(ch, method, properties, body):
    n = str(body)
    print("inside on_request")
    response = readfromdb(n)
    ch.basic_publish(exchange='',
                     routing_key=properties.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         properties.correlation_id),
                     body=response)

def writer():
    print("iam in writer")
    channelWriter.basic_consume(queue='WRITE_queue', on_message_callback=callback,auto_ack=True)
    channelWriter.start_consuming()

connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq',heartbeat = 0))
connectionrpc = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq',heartbeat = 0))
channelSyncSend = connection.channel()
channelSyncSend.exchange_declare(exchange='logs', exchange_type='fanout')
channelSyncReceive = connection.channel()
channelSyncReceive.exchange_declare(exchange='logs', exchange_type='fanout')
channelRPC = connectionrpc.channel()
channelRPC.queue_declare(queue='rpc_queue')
channelRPC.basic_qos(prefetch_count=30)
channelRPC.basic_consume(queue='rpc_queue', on_message_callback=on_request,auto_ack=True)
channelWriter = connection.channel()
channelWriter.queue_declare(queue='WRITE_queue',durable=True)
channelWriter.basic_qos(prefetch_count=30)


@zk.DataWatch(path)
def stopper(data, stat, event=None):
	print("inside datawatch")
	print(data)
	if data:
		print(data,":Data in datawatch")
		if "master" in data.decode("utf-8") :
			try :
				print("i am stopping read and rpc")
				channelSyncReceive.stop_consuming()
				#connectionrpc.close()
				channelRPC.stop_consuming()
			except Exception as e:
				print("Exception here ------",str(e))
				
			writer()
			a=1
'''

@zk.DataWatch('/zookeeper/node_worker')
def stopper(data, stat, event=None):
	print("inside datawatch")
	#channelSyncReceive.close()
	if data:
		if "master" in data :
			flagsync = 0
			flagwrite = 1
			#channelRPC.close()
			flagread = 0
		else :
			flagsync = 1
			flagwrite = 0
			#channelRPC.close()
			flagread = 1
'''

if __name__ == '__main__':
    print("in name=main")
    '''if flagsync==1:
        syncHere()
    if flagread==1:
        reader()
    if flagwrite == 1 :
        writer()
    
    result = list_master()'''
    print("HERE")
    #t2 = threading.Thread(target=reader, args=())
    #t3=threading.Thread(target=syncHere,args=())
    if os.environ["container_type"] == "master" :
        #strmaster="master,"+str(result[0])
        #print("strmaster:",strmaster)
        #strmaster1=bytes(strmaster, 'ascii')
        #zk.delete("/zookeeper/node_master", recursive=True)
        #zk.create("/zookeeper/node_master", strmaster1,ephemeral=True)
        #data, stat = zk.get("/zookeeper/node_master")
        #print("Version: %s, data: %s" % (stat.version, data.decode("utf-8")))
        writer()
    else :

        #strmaster="slave,"+str(result[0])
        #print("strslave:",strmaster)
        #strmaster1=bytes(strmaster, 'ascii')
        #zk.create("/zookeeper/node_slave", strmaster1,ephemeral=True,sequence=True)
        #t2.start()
        #t3.start()
        syncFirst()
        reader()
    app.run(host='0.0.0.0',port=8000)
