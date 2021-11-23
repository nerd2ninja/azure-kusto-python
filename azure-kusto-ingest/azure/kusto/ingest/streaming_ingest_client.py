# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License
from typing import Union, AnyStr

from typing import IO

from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from .base_ingest_client import BaseIngestClient, IngestionResult, IngestionStatus
from .descriptors import FileDescriptor, StreamDescriptor
from .ingestion_properties import IngestionProperties


class KustoStreamingIngestClient(BaseIngestClient):
    """Kusto streaming ingest client for Python.
    KustoStreamingIngestClient works with both 2.x and 3.x flavors of Python.
    All primitive types are supported.
    Tests are run using pytest.
    """

    def __init__(self, kcsb: Union[KustoConnectionStringBuilder, str]):
        """Kusto Streaming Ingest Client constructor.
        :param KustoConnectionStringBuilder kcsb: The connection string to initialize KustoClient.
        """
        self._kusto_client = KustoClient(kcsb)

    def ingest_from_file(self, file_descriptor: Union[FileDescriptor, str], ingestion_properties: IngestionProperties) -> IngestionResult:
        """Ingest from local files.
        :param file_descriptor: a FileDescriptor to be ingested.
        :param azure.kusto.ingest.IngestionProperties ingestion_properties: Ingestion properties.
        """

        stream_descriptor = StreamDescriptor.from_file_descriptor(file_descriptor)

        with stream_descriptor.stream:
            return self.ingest_from_stream(stream_descriptor, ingestion_properties)

    def ingest_from_stream(self, stream_descriptor: Union[StreamDescriptor, IO[AnyStr]], ingestion_properties: IngestionProperties) -> IngestionResult:
        """Ingest from io streams.
        :param azure.kusto.ingest.StreamDescriptor stream_descriptor: An object that contains a description of the stream to
               be ingested.
        :param azure.kusto.ingest.IngestionProperties ingestion_properties: Ingestion properties.
        """
        stream_descriptor = BaseIngestClient._prepare_stream(stream_descriptor, ingestion_properties)

        self._kusto_client.execute_streaming_ingest(
            ingestion_properties.database,
            ingestion_properties.table,
            stream_descriptor.stream,
            ingestion_properties.format.name,
            mapping_name=ingestion_properties.ingestion_mapping_reference,
        )

        return IngestionResult(IngestionStatus.SUCCESS)
