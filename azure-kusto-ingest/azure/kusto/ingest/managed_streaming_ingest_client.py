from io import SEEK_SET
from typing import TYPE_CHECKING, Union, Optional, IO, AnyStr

from azure.kusto.data import KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoApiError
from . import IngestionProperties, BlobDescriptor, StreamDescriptor, FileDescriptor
from ._retry import ExponentialRetry
from ._stream_extensions import read_until_size_or_end, chain_streams
from .base_ingest_client import BaseIngestClient, IngestionResult
from .ingest_client import QueuedIngestClient
from .streaming_ingest_client import KustoStreamingIngestClient

if TYPE_CHECKING:
    pass


class ManagedStreamingIngestClient(BaseIngestClient):
    MAX_STREAMING_SIZE_IN_BYTES = 4 * 1024 * 1024
    ATTEMPT_COUNT = 4

    def __init__(self, queued_kcsb: Union[KustoConnectionStringBuilder, str], streaming_kcsb: Optional[Union[KustoConnectionStringBuilder, str]] = None):

        if streaming_kcsb is None:
            kcsb = repr(queued_kcsb) if type(queued_kcsb) == KustoConnectionStringBuilder else queued_kcsb
            streaming_kcsb = KustoConnectionStringBuilder(kcsb.replace("https://ingest-", "https://"))

        self.queued_client = QueuedIngestClient(queued_kcsb)
        self.streaming_client = KustoStreamingIngestClient(streaming_kcsb)

    def ingest_from_file(self, file_descriptor: Union[FileDescriptor, str], ingestion_properties: IngestionProperties) -> IngestionResult:
        stream_descriptor = StreamDescriptor.from_file_descriptor(file_descriptor)

        with stream_descriptor.stream:
            return self.ingest_from_stream(stream_descriptor, ingestion_properties)

    def ingest_from_stream(self, stream_descriptor: Union[StreamDescriptor, IO[AnyStr]], ingestion_properties: IngestionProperties) -> IngestionResult:

        stream_descriptor = BaseIngestClient._prepare_stream(stream_descriptor, ingestion_properties)
        stream = stream_descriptor.stream

        buffered_stream = read_until_size_or_end(stream, self.MAX_STREAMING_SIZE_IN_BYTES + 1)

        if len(buffered_stream.getbuffer()) > self.MAX_STREAMING_SIZE_IN_BYTES:
            stream_descriptor.stream = chain_streams([buffered_stream, stream])
            return self.queued_client.ingest_from_stream(stream_descriptor, ingestion_properties)

        stream_descriptor.stream = buffered_stream

        retry = self._create_exponential_retry()
        while retry:
            try:
                return self.streaming_client.ingest_from_stream(stream_descriptor, ingestion_properties)
            except KustoApiError as e:
                error = e.get_api_error()
                if error.permanent:
                    raise
                stream.seek(0, SEEK_SET)
                retry.backoff()

        return self.queued_client.ingest_from_stream(stream_descriptor, ingestion_properties)

    def ingest_from_blob(self, blob_descriptor: BlobDescriptor, ingestion_properties: IngestionProperties):
        """
        Enqueue an ingest command from azure blobs.

        For ManagedStreamingIngestClient, this method always uses Queued Ingest, since it would be easier and faster to ingest blobs.

        To learn more about ingestion methods go to:
        https://docs.microsoft.com/en-us/azure/data-explorer/ingest-data-overview#ingestion-methods
        :param azure.kusto.ingest.BlobDescriptor blob_descriptor: An object that contains a description of the blob to be ingested.
        :param azure.kusto.ingest.IngestionProperties ingestion_properties: Ingestion properties.
        """
        return self.queued_client.ingest_from_blob(blob_descriptor, ingestion_properties)

    @staticmethod
    def _create_exponential_retry():
        return ExponentialRetry(ManagedStreamingIngestClient.ATTEMPT_COUNT)
