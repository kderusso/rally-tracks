import json
import os


class QueryParamSource:
    def __init__(self, track, params, **kwargs):
        # choose a suitable index: if there is only one defined for this track
        # choose that one, but let the user always override index
        if len(track.indices) == 1:
            default_index = track.indices[0].name
        else:
            default_index = "_all"

        self._index_name = params.get("index", default_index)
        self._cache = params.get("cache", False)
        self._params = params

        cwd = os.path.dirname(__file__)
        with open(os.path.join(cwd, "queries.json"), "r") as file:
            lines = file.readlines()
        self._queries = [line for line in lines]
        self._iters = 0
        self.infinite = True

    def partition(self, partition_index, total_partitions):
        return self

    def params(self):
        result = {"index": self._index_name, "cache": self._params.get("cache", False), "size": self._params.get("size", 10)}
        result["body"] = {
            "query": {
                "match": {
                   self._params.get("field", "body") : self._queries[self._iters]
                }
            },
            "track_total_hits": self._params.get("track_total_hits", False)
        }
        self._iters += 1
        return result

def register(registry):
    registry.register_param_source("query-param-source", QueryParamSource)