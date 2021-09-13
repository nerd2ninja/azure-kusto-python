# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License
from abc import ABCMeta, abstractmethod
from typing import List, Optional

from ._models import KustoResultTable, WellKnownDataSet, KustoStreamingResultTable
from .exceptions import KustoStreamingQueryError
from .streaming_response import ProgressiveDataSetEnumerator, FrameType


class BaseKustoResponseDataSet(metaclass=ABCMeta):
    tables: list
    tables_count: int
    tables_names: list

    @property
    @abstractmethod
    def _error_column(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def _crid_column(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def _status_column(self):
        raise NotImplementedError

    @property
    def errors_count(self) -> int:
        """Checks whether an exception was thrown."""
        query_status_table = next((t for t in self.tables if t.table_kind == WellKnownDataSet.QueryCompletionInformation), None)
        if not query_status_table:
            return 0
        min_level = 4
        errors = 0
        for row in query_status_table:
            if row[self._error_column] < 4:
                if row[self._error_column] < min_level:
                    min_level = row[self._error_column]
                    errors = 1
                elif row[self._error_column] == min_level:
                    errors += 1

        return errors

    def get_exceptions(self) -> List[str]:
        """Gets the exceptions retrieved from Kusto if exists."""
        query_status_table = next((t for t in self.tables if t.table_kind == WellKnownDataSet.QueryCompletionInformation), None)
        if not query_status_table:
            return []
        result = []
        for row in query_status_table:
            if row[self._error_column] < 4:
                result.append(
                    "Please provide the following data to Kusto: CRID='{0}' Description:'{1}'".format(row[self._crid_column], row[self._status_column])
                )
        return result

    def __iter__(self):
        return iter(self.tables)

    def __getitem__(self, key) -> KustoResultTable:
        if isinstance(key, int):
            return self.tables[key]
        try:
            return self.tables[self.tables_names.index(key)]
        except ValueError:
            raise LookupError(key)

    def __len__(self) -> int:
        return self.tables_count


class KustoResponseDataSet(BaseKustoResponseDataSet, metaclass=ABCMeta):
    """
    `KustoResponseDataSet` Represents the parsed data set carried by the response to a Kusto request.
    `KustoResponseDataSet` provides convenient methods to work with the returned result.
    The result table(s) are accessable via the @primary_results property.
    @primary_results returns a collection of `KustoResultTable`.
        It can contain more than one table when [`fork`](https://docs.microsoft.com/en-us/azure/kusto/query/forkoperator) is used.
    """

    def __init__(self, json_response):
        self.tables = [KustoResultTable(t) for t in json_response]
        self.tables_count = len(self.tables)
        self.tables_names = [t.table_name for t in self.tables]

    @property
    def primary_results(self) -> List[KustoResultTable]:
        """Returns primary results. If there is more than one returns a list."""
        if self.tables_count == 1:
            return self.tables
        primary = list(filter(lambda x: x.table_kind == WellKnownDataSet.PrimaryResult, self.tables))

        return primary


class KustoResponseDataSetV1(KustoResponseDataSet):
    """
    KustoResponseDataSetV1 is a wrapper for a V1 Kusto response.
    It parses V1 response into a convenient KustoResponseDataSet.
    To read more about V1 response structure, please check out https://docs.microsoft.com/en-us/azure/kusto/api/rest/response
    """

    _status_column = "StatusDescription"
    _crid_column = "ClientActivityId"
    _error_column = "Severity"
    _tables_kinds = {
        "QueryResult": WellKnownDataSet.PrimaryResult,
        "QueryProperties": WellKnownDataSet.QueryProperties,
        "QueryStatus": WellKnownDataSet.QueryCompletionInformation,
    }

    def __init__(self, json_response: dict):
        super(KustoResponseDataSetV1, self).__init__(json_response["Tables"])
        if self.tables_count <= 2:
            self.tables[0].table_kind = WellKnownDataSet.PrimaryResult
            self.tables[0].table_id = 0

            if self.tables_count == 2:
                self.tables[1].table_kind = WellKnownDataSet.QueryProperties
                self.tables[1].table_id = 1
        else:
            toc = self.tables[-1]
            toc.table_kind = WellKnownDataSet.TableOfContents
            toc.table_id = self.tables_count - 1
            for i in range(self.tables_count - 1):
                self.tables[i].table_name = toc[i]["Name"]
                self.tables[i].table_id = toc[i]["Id"]
                self.tables[i].table_kind = self._tables_kinds[toc[i]["Kind"]]


class KustoResponseDataSetV2(KustoResponseDataSet):
    """
    KustoResponseDataSetV2 is a wrapper for a V2 Kusto response.
    It parses V2 response into a convenient KustoResponseDataSet.
    To read more about V2 response structure, please check out https://docs.microsoft.com/en-us/azure/kusto/api/rest/response2
    """

    _status_column = "Payload"
    _error_column = "Level"
    _crid_column = "ClientRequestId"

    def __init__(self, json_response: List[dict]):
        super(KustoResponseDataSetV2, self).__init__([t for t in json_response if t["FrameType"] == "DataTable"])


class KustoStreamingResponseDataSet(BaseKustoResponseDataSet):
    _status_column = "Payload"
    _error_column = "Level"
    _crid_column = "ClientRequestId"

    current_primary_results_table: KustoStreamingResultTable
    """
       The current primary results table which provides an interface to stream its rows.
       Becomes invalidated after a successful call to `next_primary_results_table` or `read_rest_of_tables` 
    """

    def extract_tables_until_primary_result(self):
        while True:
            table = next(self.streamed_data)
            if table["FrameType"] != FrameType.DataTable:
                continue
            if self.streamed_data.started_primary_results:
                self.current_primary_results_table = KustoStreamingResultTable(table)
                self.tables.append(self.current_primary_results_table)
                break
            else:
                self.tables.append(KustoResultTable(table))

    def __init__(self, streamed_data: ProgressiveDataSetEnumerator):
        self.tables = []
        self.streamed_data = streamed_data
        self.have_read_rest_of_tables = False
        self.extract_tables_until_primary_result()

    def next_primary_results_table(self, ensure_current_finished=True) -> Optional[KustoStreamingResultTable]:
        if self.have_read_rest_of_tables:
            return None
        if ensure_current_finished and not self.current_primary_results_table.finished:
            raise KustoStreamingQueryError(
                "Tried retrieving a new primary_result table before the old one was finished. To override pass `ensure_current_finished=False`"
            )

        table = next(self.streamed_data)
        if self.streamed_data.finished_primary_results:
            # If we're finished with primary results, we want to retrieve the rest of the tables
            if table["FrameType"] == FrameType.DataTable:
                self.tables.append(KustoResultTable(table))
            self.read_rest_of_tables()
        else:
            self.current_primary_results_table = KustoStreamingResultTable(table)
            return self.current_primary_results_table

    def read_rest_of_tables(self, ensure_primary_tables_finished=True):
        if self.have_read_rest_of_tables:
            return

        if ensure_primary_tables_finished and not self.streamed_data.finished_primary_results:
            raise KustoStreamingQueryError(
                "Tried retrieving all of the tables before the primary_results are finished. To override pass `ensure_primary_tables_finished=False`"
            )

        self.tables.extend(KustoResultTable(t) for t in self.streamed_data if t["FrameType"] == FrameType.DataTable)
        self.have_read_rest_of_tables = True

    @property
    def errors_count(self) -> int:
        if not self.have_read_rest_of_tables:
            raise KustoStreamingQueryError(
                "Unable to get errors count before reading all of the tables. Advance `next_primary_results_table` to the end, or use `read_rest_of_tables`"
            )
        return super().errors_count

    def get_exceptions(self) -> List[str]:
        if not self.have_read_rest_of_tables:
            raise KustoStreamingQueryError(
                "Unable to get errors count before reading all of the tables. Advance `next_primary_results_table` to the end, or use `read_rest_of_tables`"
            )
        return super().get_exceptions()

    def __getitem__(self, key) -> KustoResultTable:
        if isinstance(key, int):
            return self.tables[key]
        try:
            return next(t for t in self.tables if t.table_name == key)
        except StopIteration:
            raise LookupError(key)

    def __len__(self) -> int:
        return len(self.tables)
