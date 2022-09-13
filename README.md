# amundsen
Instalação do Amundsen no ubuntu 20.04.4 LTS

## Pré Requisitos
- docker-compose 1.29.2-1 
- airflow 2.2.2.

## Airflow
### Setup
```
git clone https://github.com/weslleyfelix/amundsen.git
```
```
mkdir -p /opt/airflow/dags /opt/airflow/logs /opt/airflow/plugins /opt/airflow/data

chmod -R 777 /opt/airflow
```
```
cd airflow
```
```
docker-compose up airflow-init
docker-compose up -d
```

### Default url 
http://localhost:8080

### Default Username
airflow

### Default Password
airflow

## Amundsen

### Default url Amundsen
http://localhost:5000

### Default Username Amundsen
-

### Default Password Amundsen
-

### Default url Neo4j
http://localhost:7474/browser

### Default Username Neo4j
-

### Default Password Neo4j
-

### Default url Elasticsearch
http://localhost:9200

### Default Username Elasticsearch
-

### Default Password Elasticsearch
-
