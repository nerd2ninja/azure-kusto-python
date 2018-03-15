# Microsoft Azure Kusto Library for Python
Kusto Python Client Library provides the capability to query Kusto clusters with Python.<br>
Kusto Python Ingest Client is a python library that allows sending data to Kusto service - i.e. ingest data. 

## Install
### Option 1: Via PyPi
To install via the Python Package Index (PyPI), type:

* pip install azure-kusto-data
* pip install azure-kusto-ingest

### Option 2: Source Via Git
To get the source code of the SDK via git just type:

git clone git://github.com/Azure/azure-kusto-python.git

cd ./azure-kusto-python/azure-kusto-data<br>
python setup.py install

cd ../azure-kusto-ingest<br>
python setup.py install

### Option 3: Source Zip
Download a zip of the code via GitHub or PyPi. Then follow the same instructions in option 2.

## Minimum Requirements
* Python 2.7, 3.4, 3.5, or 3.6.
* See setup.py for dependencies

## Authentication methods:

* AAD Username/password - Provide your AAD username and password to Kusto client.
* AAD application - Provide app ID and app secret to Kusto client.
* AAD code - Provide only your AAD username, and authenticate yourself using a code, generated by ADAL.

## Samples:
More samples can be found at the tests folder of each of the packages.

### Sample: Query Kusto using Python

```python
from azure.kusto.data import KustoClient

kusto_cluster = 'https://help.kusto.windows.net'

# In case you want to authenticate with AAD application.
client_id = '<insert here your AAD application ID>'
client_secret = '<insert here your AAD application key>'
client = KustoClient(kusto_cluster=kusto_cluster, client_id=client_id, client_secret=client_secret)

# In case you want to authenticate with AAD user.
client = KustoClient(kusto_cluster=kusto_cluster)

kusto_database = 'Samples'
response = client.execute(kusto_database, 'StormEvents | take 10')

client = KustoClient('https://kustolab.kusto.windows.net')
response = client.execute("ML", ".show version")
query = '''
let max_t = datetime(2016-09-03);
service_traffic
| make-series num=count() on TimeStamp in range(max_t-5d, max_t, 1h) by OsVer
'''
data_frame = client.execute_query("ML", query).to_dataframe()
```

### Sample: Ingesting data into Kusto using Python

```python
from azure.kusto.ingest import KustoIngestClient, IngestionProperties, FileDescriptor, BlobDescriptor

ingestion_properties = IngestionProperties(database="database name", table="table name", format=DataFormat.csv)

ingest_client = KustoIngestClient("https://ingest-clustername.kusto.windows.net", username="username@microsoft.com")
ingest_client = KustoIngestClient("https://ingest-clustername.kusto.windows.net", client_id="aad app id", client_secret="secret")

descriptor = FileDecriptor("E:\\filePath.csv", 3333) # 3333 is the raw size of the data.
ingest_client.__IngestFromMultipleFiles__([descriptor], deleteSourcesOnSuccess=True, ingestion_properties)  

ingest_client.__IngestFromMultipleFiles__(["E:\\filePath.csv"], deleteSourcesOnSuccess=True, ingestion_properties)  
ingest_client.__IngestFromMultipleBlobs__([BlobDescriptor("https://path-to-blob.csv.gz?sas", 10)], # 10 is the raw size of the data.
                                          deleteSourcesOnSuccess=True, 
                                          ingestion_properties=ingestion_properties)  
```