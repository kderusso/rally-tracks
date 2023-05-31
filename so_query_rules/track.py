import random
import os


class QueryParamSource:
    # mandated by the Rally API
    # noinspection PyUnusedLocal
    def __init__(self, track, params, **kwargs):
        self._params = params
        # here we read the queries data file into arrays which we'll then later use randomly.
        self.qtext = []
        # be predictably random. The seed has been chosen by a fair dice roll. ;)
        # TODO: parameterize
        random.seed(4)
        cwd = os.path.dirname(__file__)
        with open(os.path.join(cwd, "queries.txt"), "r") as f:
            self.qtext = f.readlines()
        self.qtext = [line.strip() for line in self.qtext]

    def partition(self, partition_index, total_partitions):
        return self

    def size(self):
        return 1


class RuleQuery(QueryParamSource):
    def params(self):
        query_text = "%s" % random.choice(self.qtext)
        result = {
            "body": {
                "query": {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["title^5", "body"]
                    }
                },
                "size": 10,
                "from": 0
            },
            "index": "so",
            "type": "doc",
            "use_request_cache": self._params["cache"]
        }
        return result


def register(registry):
    registry.register_param_source(
        "rules-source", RuleQuery)
