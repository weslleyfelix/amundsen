# amundsen
Instalação do Amundsen no ubuntu 20.04.4 LTS com o docker compose.


## Pré Requisitos
- docker-compose 1.29.2-1 
- airflow 2.1.4.

## Documentação
- https://www.amundsen.io/amundsen/installation/
- https://airflow.apache.org/docs/apache-airflow/stable/installation/index.html


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

- Default Username: airflow
- Default Password: airflow

## Amundsen

### Default url Amundsen
http://localhost:5000


### Default url Neo4j
http://localhost:7474/browser

- Default Username: neo4j
- Default Password: neo4j

### Default url Elasticsearch
http://localhost:9200


