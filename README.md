# amundsen
Instalação do Amundsen no ubuntu 20.04.4 LTS

## Pré Requisitos
- docker-compose 1.29.2-1 
- airflow 2.2.2.

## Setup Airflow
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
docker-compose up -d
```

## Default url
http://localhost:8080

## Default Username
airflow

## Default Password
airflow
