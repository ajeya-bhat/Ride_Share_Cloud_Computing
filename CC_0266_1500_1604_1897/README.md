# Cloud Computing Final Project and Assignments Readme

### Assignment1
    pip3 install gunicorn flask flask Flask-SQLAlchemy requests
- Copy the Assignment1 folder
- Install nginx and remove default file in sites-enabled and add nginx_conf.txt
- Change the server_name according to your instance public ip
- Go inside Assignment1 folder
- gunicorn3 --bind 127.0.0.1:5000 -w 4 assignment1:app


### Assignment2
     pip3 install flask flask Flask-SQLAlchemy requests
- #### Add the users and rides folder
- #### Install docker
     sudo docker network create --subnet 172.255.0.0/16 mynet1
- #### Go to users folder
     sudo docker build -t users:latest .<br />
     sudo docker run -it -d --name users -p 8080:80 --net mynet1 --ip 172.255.0.3 users:latest
- #### Go to rides folder
     sudo docker build -t rides:latest .<br />
     sudo docker run -it -d --name rides -p 8000:80 --net mynet1 --ip 172.255.0.2 rides:latest
     
### Assignment3
- #### Create two instances and configure Target groups for them 
- #### Add the Assignment3 user and rides folders to respective instances
- #### Configure Path Based Load Balancer,and set the Targets for the respective paths
- #### In Users Instance,go to the folder with Dockerfile and run the below two commands
     sudo docker build -t users:latest .<br />
     sudo docker run -it -d --name users -p 8000:80 users:latest
- #### In Rides Instance,go to the folder with Dockerfile and run the below two commands
     sudo docker build -t rides:latest .<br />
     sudo docker run -it -d --name rides -p 8000:80 rides:latest

### Final Project
- #### In usermgmt.py and ridemgmt.py the IP address of the Database instance has to be updated. 
- #### All the read requests and write requests  are sent to the worker file.
- #### Configure Path Based Load Balancer,and set the Targets for the respective paths
- #### In Users Instance,go to the folder with Dockerfile and run the below two commands
     sudo docker build -t users:latest .<br />
     sudo docker run -it -d --name users -p 8000:80 users:latest
- #### In Rides Instance,go to the folder with Dockerfile and run the below two commands
     sudo docker build -t rides:latest .<br />
     sudo docker run -it -d --name users -p 8000:80 rides:latest
- #### In DBaaS Instance, run the following command 
     ./cc.sh

