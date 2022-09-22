# É necessário colocar este arquivo dentro da pasta de DAGS do AIRFLOW
# Verificar no arquivo de configuração do AIRFLOW o path dos DAGS
# dags_folder = /root/airflow/dags

# Importando módulos
# Módulos do python
import uuid
import logging
from datetime import datetime, timedelta

# Módulos do Airflow
from airflow import DAG  # noqa
from airflow import macros  # noqa
from airflow.operators.python_operator import PythonOperator  # noqa
from elasticsearch import Elasticsearch
from pyhocon import ConfigFactory, ConfigTree  # noqa: F401

import concurrent.futures

from collections import namedtuple
from typing import (  # noqa: F401
    Dict, Iterator, List, Optional, Union,
)

# Módulos do spark
from pyspark.sql import SparkSession
from pyspark.sql.catalog import Table
from pyspark.sql.utils import AnalysisException

# Módulos para importar os metadados no backend amundsen
from databuilder.job.job import DefaultJob
from databuilder.task.task import DefaultTask
from databuilder.transformer.base_transformer import NoopTransformer

from databuilder.extractor.neo4j_extractor import Neo4jExtractor
from databuilder.extractor.neo4j_search_data_extractor import Neo4jSearchDataExtractor
from databuilder.extractor.postgres_metadata_extractor import PostgresMetadataExtractor
from databuilder.extractor.sql_alchemy_extractor import SQLAlchemyExtractor

from databuilder.loader.file_system_elasticsearch_json_loader import FSElasticsearchJSONLoader
from databuilder.loader.file_system_neo4j_csv_loader import FsNeo4jCSVLoader

from databuilder.publisher import neo4j_csv_publisher
from databuilder.publisher.elasticsearch_publisher import ElasticsearchPublisher
from databuilder.publisher.neo4j_csv_publisher import Neo4jCsvPublisher

# Módulos para extrair os dados da origem delta
from databuilder.extractor.base_extractor import Extractor
from databuilder.models.table_last_updated import TableLastUpdated
from databuilder.models.table_metadata import ColumnMetadata, TableMetadata


# Vamos criar um objeto DAG
dag_args = {
    'concurrency': 10,
    # One dagrun at a time
    'max_active_runs': 1,
    'catchup': False
}

default_args = {
    'owner': 'amundsen',
    'depends_on_past': False,
    # Exemplo: Inicia em 20 de Setembro de 2022
    'start_date': datetime(2022, 9, 20),    
    'email': ['weslley.felix@deal.com.br'],
    'email_on_failure': False,
    'email_on_retry': False,
    # Em caso de erros, tente rodar novamente apenas 1 vez
    'retries': 1,
    'priority_weight': 10,
    # Tente novamente após 5 minutos depois do erro
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=120),
    
    # Execute uma vez por dia as 11AM 
    'schedule_interval': '0 11 * * *',
}

# Exemplo de definição de schedule 
# .---------------- minuto (0 - 59)
# |  .------------- hora (0 - 23)
# |  |  .---------- dia do mês (1 - 31)
# |  |  |  .------- mês (1 - 12) 
# |  |  |  |  .---- dia da semana (0 - 6) (Domingo=0 or 7)
# |  |  |  |  |
# *  *  *  *  * (nome do usuário que vai executar o comando)


# Extrator Delta
TableKey = namedtuple('TableKey', ['schema', 'table_name'])
LOGGER = logging.getLogger(__name__)

## Coletando os metadados de colunas
class ScrapedColumnMetadata(object):
    def __init__(self, name: str, data_type: str, description: Optional[str], sort_order: int):
        self.name = name
        self.data_type = data_type
        self.description = description
        self.sort_order = sort_order
        self.is_partition = False
        self.attributes: Dict[str, str] = {}

    def set_is_partition(self, is_partition: bool) -> None:
        self.is_partition = is_partition

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScrapedColumnMetadata):
            return False
        return (self.name == other.name and
                self.data_type == other.data_type and
                self.description == other.description and
                self.sort_order == other.sort_order and
                self.is_partition == other.is_partition and
                self.attributes == other.attributes)

    def __repr__(self) -> str:
        return f'{self.name}:{self.data_type}'


## Classes que utilizam os extratores delta para coletar os metadados de tabelas
class ScrapedTableMetadata(object):
    LAST_MODIFIED_KEY = 'lastModified'
    DESCRIPTION_KEY = 'description'
    TABLE_FORMAT_KEY = 'format'

    def __init__(self, schema: str, table: str):
        self.schema: str = schema
        self.table: str = table
        self.table_detail: Optional[Dict] = None
        self.view_detail: Optional[Dict] = None
        self.is_view: bool = False
        self.failed_to_scrape: bool = False
        self.columns: Optional[List[ScrapedColumnMetadata]] = None

    def set_table_detail(self, table_detail: Dict) -> None:
        self.table_detail = table_detail
        self.is_view = False
        self.failed_to_scrape = False

    def set_view_detail(self, view_detail: Dict) -> None:
        self.view_detail = view_detail
        self.is_view = True
        self.failed_to_scrape = False

    def get_details(self) -> Optional[Dict]:
        if self.is_view:
            return self.view_detail
        else:
            return self.table_detail

    def get_full_table_name(self) -> str:
        return self.schema + "." + self.table

    def set_failed_to_scrape(self) -> None:
        self.failed_to_scrape = True

    def set_columns(self, column_list: List[ScrapedColumnMetadata]) -> None:
        self.columns = column_list

    def get_last_modified(self) -> Optional[datetime]:
        details = self.get_details()
        if details and self.LAST_MODIFIED_KEY in details:
            return details[self.LAST_MODIFIED_KEY]
        else:
            return None

    def get_table_description(self) -> Optional[str]:
        details = self.get_details()
        if details and self.DESCRIPTION_KEY in details:
            return details[self.DESCRIPTION_KEY]
        else:
            return None

    def is_delta_table(self) -> bool:
        details = self.get_details()
        if details and self.TABLE_FORMAT_KEY in details:
            return details[self.TABLE_FORMAT_KEY].lower() == 'delta'
        else:
            return False

    def __repr__(self) -> str:
        return f'{self.schema}.{self.table}'


class DeltaLakeMetadataExtractor(Extractor):
    """
    Extrai Metadados do Delta Lake.
    Isso requer a execução de uma sessão do Spark que tenha um metastore do hive preenchido com todas as tabelas delta
    que voce deseja importar.
    """
    # CONFIG KEYS
    DATABASE_KEY = "database"
    # Se você deseja excluir esquemas específicos
    EXCLUDE_LIST_SCHEMAS_KEY = "exclude_list"
    # Se você deseja incluir apenas esquemas específicos
    SCHEMA_LIST_KEY = "schema_list"
    CLUSTER_KEY = "cluster"
    # Por padrão, isso só processará e emitirá tabelas delta-lake, mas pode suportar todos os tipos de tabela hive.
    DELTA_TABLES_ONLY = "delta_tables_only"
    DEFAULT_CONFIG = ConfigFactory.from_dict({DATABASE_KEY: "delta",
                                              EXCLUDE_LIST_SCHEMAS_KEY: [],
                                              SCHEMA_LIST_KEY: [],
                                              DELTA_TABLES_ONLY: True})
    PARTITION_COLUMN_TAG = 'is_partition'

    def init(self, conf: ConfigTree) -> None:
        self.conf = conf.with_fallback(DeltaLakeMetadataExtractor.DEFAULT_CONFIG)
        self._extract_iter = None  # type: Union[None, Iterator]
        self._cluster = self.conf.get_string(DeltaLakeMetadataExtractor.CLUSTER_KEY)
        self._db = self.conf.get_string(DeltaLakeMetadataExtractor.DATABASE_KEY)
        self.exclude_list = self.conf.get_list(DeltaLakeMetadataExtractor.EXCLUDE_LIST_SCHEMAS_KEY)
        self.schema_list = self.conf.get_list(DeltaLakeMetadataExtractor.SCHEMA_LIST_KEY)
        self.delta_tables_only = self.conf.get_bool(DeltaLakeMetadataExtractor.DELTA_TABLES_ONLY)

    def set_spark(self, spark: SparkSession) -> None:
        self.spark = spark

    def extract(self) -> Union[TableMetadata, TableLastUpdated, None]:
        if not self._extract_iter:
            self._extract_iter = self._get_extract_iter()
        try:
            return next(self._extract_iter)
        except StopIteration:
            return None

    def get_scope(self) -> str:
        return 'extractor.delta_lake_table_metadata'

    def _get_extract_iter(self) -> Iterator[Union[TableMetadata, TableLastUpdated, None]]:
        """
        Dada uma lista de esquemas ou uma lista de esquemas de exclusão,
        ele consultará o metastore do hive e acessará o log delta
        para obter todos os metadados de suas tabelas delta. Produzirá:
         - metadados de tabelas e colunas
         - última informação atualizada
        """
        if self.schema_list:
            LOGGER.info("working on %s", self.schema_list)
            tables = self.get_all_tables(self.schema_list)
        else:
            LOGGER.info("fetching all schemas")
            LOGGER.info("Excluding: %s", self.exclude_list)
            schemas = self.get_schemas(self.exclude_list)
            LOGGER.info("working on %s", schemas)
            tables = self.get_all_tables(schemas)
        # TODO add the programmatic information as well?
        # TODO add watermarks
        scraped_tables = self.scrape_all_tables(tables)
        for scraped_table in scraped_tables:
            if not scraped_table:
                continue
            if self.delta_tables_only and not scraped_table.is_delta_table():
                LOGGER.info("Skipping none delta table %s", scraped_table.table)
                continue
            else:
                yield self.create_table_metadata(scraped_table)
                last_updated = self.create_table_last_updated(scraped_table)
                if last_updated:
                    yield last_updated

    def get_schemas(self, exclude_list: List[str]) -> List[str]:
        '''Retorna todos os esquemas.'''
        schemas = self.spark.catalog.listDatabases()
        ret = []
        for schema in schemas:
            if schema.name not in exclude_list:
                ret.append(schema.name)
        return ret

    def get_all_tables(self, schemas: List[str]) -> List[Table]:
        '''Retorna todas as tabelas.'''
        ret = []
        for schema in schemas:
            ret.extend(self.get_tables_for_schema(schema))
        return ret

    def get_tables_for_schema(self, schema: str) -> List[Table]:
        '''Retorna todas as tabelas de um esquema específico.'''
        return self.spark.catalog.listTables(schema)

    def scrape_all_tables(self, tables: List[Table]) -> List[Optional[ScrapedTableMetadata]]:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.scrape_table, table) for table in tables]
        scraped_tables = [f.result() for f in futures]
        return scraped_tables

    def scrape_table(self, table: Table) -> Optional[ScrapedTableMetadata]:
        '''Pega um objeto de tabela e cria um objeto com os metadados.'''
        met = ScrapedTableMetadata(schema=table.database, table=table.name)
        table_name = met.get_full_table_name()
        if table.tableType and table.tableType.lower() != 'view':
            table_detail = self.scrape_table_detail(table_name)
            if table_detail is None:
                LOGGER.error("Failed to parse table " + table_name)
                met.set_failed_to_scrape()
                return None
            else:
                LOGGER.info("Successfully parsed table " + table_name)
                met.set_table_detail(table_detail)
        else:
            view_detail = self.scrape_view_detail(table_name)
            if view_detail is None:
                LOGGER.error("Failed to parse view " + table_name)
                met.set_failed_to_scrape()
                return None
            else:
                LOGGER.info("Successfully parsed view " + table_name)
                met.set_view_detail(view_detail)
        columns = self.fetch_columns(met.schema, met.table)
        if not columns:
            LOGGER.error("Failed to parse columns for " + table_name)
            return None
        else:
            met.set_columns(columns)
            return met

    def scrape_table_detail(self, table_name: str) -> Optional[Dict]:
        try:
            table_details_df = self.spark.sql(f"describe detail {table_name}")
            table_detail = table_details_df.collect()[0]
            return table_detail.asDict()
        except Exception as e:
            LOGGER.error(e)
            return None

    def scrape_view_detail(self, view_name: str) -> Optional[Dict]:
        # TODO the blanket try catches need to be changed
        describeExtendedOutput = []
        try:
            describeExtendedOutput = self.spark.sql(f"describe extended {view_name}").collect()
        except Exception as e:
            LOGGER.error(e)
            return None
        view_detail = {}
        startAdding = False
        for row in describeExtendedOutput:
            row_dict = row.asDict()
            if startAdding:
                view_detail[row_dict['col_name']] = row_dict['data_type']
            if "# Detailed Table" in row_dict['col_name']:
                # Then start parsing
                startAdding = True
        return view_detail

    def fetch_columns(self, schema: str, table: str) -> List[ScrapedColumnMetadata]:
        '''Isso busca colunas da tabela delta, que infelizmente
           não estão replicadas em spark.catalog.listColumns.'''
        raw_columns = []
        try:
            raw_columns = self.spark.sql(f"describe {schema}.{table}").collect()
        except AnalysisException as e:
            LOGGER.error(e)
            return raw_columns
        parsed_columns = {}
        partition_cols = False
        sort_order = 0
        for row in raw_columns:
            col_name = row['col_name']
            # NOTE: the behavior of describe has changed between spark 2 and spark 3
            if col_name == '' or '#' in col_name:
                partition_cols = True
                continue
            if not partition_cols:
                column = ScrapedColumnMetadata(
                    name=row['col_name'],
                    description=row['comment'] if row['comment'] else None,
                    data_type=row['data_type'],
                    sort_order=sort_order
                )
                parsed_columns[row['col_name']] = column
                sort_order += 1
            else:
                if row['data_type'] in parsed_columns:
                    LOGGER.debug(f"Adding partition column table for {row['data_type']}")
                    parsed_columns[row['data_type']].set_is_partition(True)
                elif row['col_name'] in parsed_columns:
                    LOGGER.debug(f"Adding partition column table for {row['col_name']}")
                    parsed_columns[row['col_name']].set_is_partition(True)
        return list(parsed_columns.values())

    def create_table_metadata(self, table: ScrapedTableMetadata) -> TableMetadata:
        '''Cria o objeto de metadados da tabela Amundsen a partir do objeto ScrapedTableMetadata.'''
        amundsen_columns = []
        if table.columns:
            for column in table.columns:
                amundsen_columns.append(
                    ColumnMetadata(name=column.name,
                                   description=column.description,
                                   col_type=column.data_type,
                                   sort_order=column.sort_order)
                )
        description = table.get_table_description()
        return TableMetadata(self._db,
                             self._cluster,
                             table.schema,
                             table.table,
                             description,
                             amundsen_columns,
                             table.is_view)

    def create_table_last_updated(self, table: ScrapedTableMetadata) -> Optional[TableLastUpdated]:
        '''Cria o objeto de metadados da última atualização da tabela Amundsen a partir do objeto ScrapedTableMetadata.'''
        last_modified = table.get_last_modified()
        if last_modified:
            return TableLastUpdated(table_name=table.table,
                                    last_updated_time_epoch=int(last_modified.timestamp()),
                                    schema=table.schema,
                                    db=self._db,
                                    cluster=self._cluster)
        else:
            return None

## Parâmetros e metodos usados na publicação do backend amundsen         

# NEO4J acessos
NEO4J_ENDPOINT = 'bolt://172.21.0.3:7687'
neo4j_endpoint = NEO4J_ENDPOINT
neo4j_user = 'neo4j'
neo4j_password = 'test'

# Elasticsearch acessos
es = Elasticsearch([
    {'host': '172.21.0.2', 'port': '9200'},
])

SUPPORTED_SCHEMAS = ['public']
# String format - ('schema1', schema2', .... 'schemaN')
SUPPORTED_SCHEMA_SQL_IN_CLAUSE = "('{schemas}')".format(schemas="', '".join(SUPPORTED_SCHEMAS))

OPTIONAL_TABLE_NAMES = ''

# Airflow acessos
def connection_string():
    user = 'airflow'
    password = 'airflow'
    host = '172.21.0.8'
    port = '5432'
    db = 'airflow'
    return "postgresql://%s:%s@%s:%s/%s" % (user, password, host, port, db)


# Método para publicar o csv com metadados no NEO4J
def create_table_extract_job():
    where_clause_suffix = f'st.schemaname in {SUPPORTED_SCHEMA_SQL_IN_CLAUSE}'

    tmp_folder = '/var/tmp/amundsen/table_metadata'
    node_files_folder = f'{tmp_folder}/nodes/'
    relationship_files_folder = f'{tmp_folder}/relationships/'

    job_config = ConfigFactory.from_dict({
        f'extractor.postgres_metadata.{PostgresMetadataExtractor.WHERE_CLAUSE_SUFFIX_KEY}': where_clause_suffix,
        f'extractor.postgres_metadata.{PostgresMetadataExtractor.USE_CATALOG_AS_CLUSTER_NAME}': True,
        f'extractor.postgres_metadata.extractor.sqlalchemy.{SQLAlchemyExtractor.CONN_STRING}': connection_string(),
        f'loader.filesystem_csv_neo4j.{FsNeo4jCSVLoader.NODE_DIR_PATH}': node_files_folder,
        f'loader.filesystem_csv_neo4j.{FsNeo4jCSVLoader.RELATION_DIR_PATH}': relationship_files_folder,
        f'publisher.neo4j.{neo4j_csv_publisher.NODE_FILES_DIR}': node_files_folder,
        f'publisher.neo4j.{neo4j_csv_publisher.RELATION_FILES_DIR}': relationship_files_folder,
        f'publisher.neo4j.{neo4j_csv_publisher.NEO4J_END_POINT_KEY}': neo4j_endpoint,
        f'publisher.neo4j.{neo4j_csv_publisher.NEO4J_USER}': neo4j_user,
        f'publisher.neo4j.{neo4j_csv_publisher.NEO4J_PASSWORD}': neo4j_password,
        f'publisher.neo4j.{neo4j_csv_publisher.JOB_PUBLISH_TAG}': 'unique_tag',  # should use unique tag here like {ds}
    })
    job = DefaultJob(conf=job_config,
                     task=DefaultTask(extractor=PostgresMetadataExtractor(), loader=FsNeo4jCSVLoader()),
                     publisher=Neo4jCsvPublisher())
    job.launch()

# Método para publicar o json com índices de pesquisa no ElasticSearch
def create_es_publisher_sample_job():
    # O loader salva os dados nesse local e o editor os lê daqui
    extracted_search_data_path = '/var/tmp/amundsen/search_data.json'

    task = DefaultTask(loader=FSElasticsearchJSONLoader(),
                       extractor=Neo4jSearchDataExtractor(),
                       transformer=NoopTransformer())

    # elastic search client instance
    elasticsearch_client = es
    # nome exclusivo do novo índice no Elasticsearch
    elasticsearch_new_index_key = f'tables{uuid.uuid4()}'
    # relacionado ao tipo de mapeamento de /databuilder/publisher/elasticsearch_publisher.py#L38
    elasticsearch_new_index_key_type = 'table'
    # alias para o Elasticsearch usado em amundsensearchlibrary/search_service/config.py as an index
    elasticsearch_index_alias = 'table_search_index'

    job_config = ConfigFactory.from_dict({
        'extractor.search_data.entity_type': 'table',
        f'extractor.search_data.extractor.neo4j.{Neo4jExtractor.GRAPH_URL_CONFIG_KEY}': neo4j_endpoint,
        f'extractor.search_data.extractor.neo4j.{Neo4jExtractor.MODEL_CLASS_CONFIG_KEY}':
            'databuilder.models.table_elasticsearch_document.TableESDocument',
        f'extractor.search_data.extractor.neo4j.{Neo4jExtractor.NEO4J_AUTH_USER}': neo4j_user,
        f'extractor.search_data.extractor.neo4j.{Neo4jExtractor.NEO4J_AUTH_PW}': neo4j_password,
        f'loader.filesystem.elasticsearch.{FSElasticsearchJSONLoader.FILE_PATH_CONFIG_KEY}': extracted_search_data_path,
        f'loader.filesystem.elasticsearch.{FSElasticsearchJSONLoader.FILE_MODE_CONFIG_KEY}': 'w',
        f'publisher.elasticsearch.{ElasticsearchPublisher.FILE_PATH_CONFIG_KEY}': extracted_search_data_path,
        f'publisher.elasticsearch.{ElasticsearchPublisher.FILE_MODE_CONFIG_KEY}': 'r',
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_CLIENT_CONFIG_KEY}':
            elasticsearch_client,
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_NEW_INDEX_CONFIG_KEY}':
            elasticsearch_new_index_key,
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_DOC_TYPE_CONFIG_KEY}':
            elasticsearch_new_index_key_type,
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_ALIAS_CONFIG_KEY}':
            elasticsearch_index_alias
    })

    job = DefaultJob(conf=job_config,
                     task=task,
                     publisher=ElasticsearchPublisher())
    job.launch()

# Vamos agora informar ao nosso DAG o que ele deve fazer. 
with DAG(    
    dag_id='dag_delta_lake_metadata_amundsen',
    default_args=default_args,
    schedule_interval=None,
    tags=['exemplo'],
    **dag_args
) as dag: 

    # As tarefas abaixo usam o operador PythonOperator
    
    delta_table_last_updated_job = PythonOperator(
        task_id='delta_table_last_updated_job',     
        python_callable=DeltaLakeMetadataExtractor.create_table_last_updated
    )

    delta_table_table_metadata_job = PythonOperator(
        task_id='delta_table_table_metadata_job',     
        python_callable=DeltaLakeMetadataExtractor.create_table_metadata
    )

    neo4j_metadata_job = PythonOperator(
        task_id='neo4j_metadata_job',
        
        python_callable=create_table_extract_job
    )

    elasticsearch_index_job = PythonOperator(
        task_id='elasticsearch_index_job',
        python_callable=create_es_publisher_sample_job
    )

    # Ordem de execução dos Operators/Tasks
    ## Atualização da pesquisa no elasticsearch executada após a atualização dos metadados da tabela
    delta_table_last_updated_job>> delta_table_table_metadata_job>> neo4j_metadata_job >> elasticsearch_index_job
    
    
