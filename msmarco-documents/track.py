import csv
import json
import os
from collections import defaultdict
from typing import Dict

Qrels = Dict[str, Dict[str, int]]
Results = Dict[str, Dict[str, float]]


def calc_ndcg(qrels: Qrels, results: Results, k_list: list):
    import pytrec_eval as pe

    for qid, rels in results.items():
        for pid in list(rels):
            if qid == pid:
                results[qid].pop(pid)

    scores = defaultdict(float)

    metrics = ["ndcg_cut"]
    pytrec_strings = {f"{metric}.{','.join([str(k) for k in k_list])}" for metric in metrics}
    evaluator = pe.RelevanceEvaluator(qrels, pytrec_strings)
    pytrec_scores = evaluator.evaluate(results)

    for query_id in pytrec_scores.keys():
        for metric in metrics:
            for k in k_list:
                scores[f"{metric}@{k}"] += pytrec_scores[query_id][f"{metric}_{k}"]

    queries_count = len(pytrec_scores.keys())
    if queries_count == 0:
        return scores

    for metric in metrics:
        for k in k_list:
            scores[f"{metric}@{k}"] = float(scores[f"{metric}@{k}"] / queries_count)

    return scores


def read_qrels(qrels_input_file):
    qrels = defaultdict(dict)
    with open(qrels_input_file, "r") as input_file:
        tsv_reader = csv.reader(input_file, delimiter="\t")
        for query_id, doc_id, score in tsv_reader:
            qrels[query_id][doc_id] = int(score)
    return qrels


def generate_match_query(field, query, boost=1.0):
    return {"retriever": {"standard": {"query": {"match": {field: query}}}}}


def generate_match_query_with_reranker(field, rerank_field, query, snippets, boost=1.0):
    if snippets:
        return {
            "retriever": {
                "text_similarity_reranker": {
                    "retriever": {"standard": {"query": {"match": {field: query}}}},
                    "field": rerank_field,
                    "inference_text": query,
                }
            }
        }
    else:
        return {
            "retriever": {
                "text_similarity_reranker": {
                    "retriever": {"standard": {"query": {"match": {field: query}}}},
                    "field": rerank_field,
                    "inference_text": query,
                    "snippets": {},
                }
            }
        }


class QueryParamsSource:
    def __init__(self, track, params, **kwargs):
        if len(track.indices) == 1:
            default_index = track.indices[0].name
        else:
            default_index = "_all"

        self._index_name = params.get("index", default_index)
        self._cache = params.get("cache", False)
        self._size = params.get("size", 10)
        self._query_file = params.get("query_source", "queries.json")
        self._query_strategy = params.get("query_strategy", "bm25")
        self._field = params.get("field", "content")
        self._rerank_field = params.get("rerank_field", "content")
        self._rerank = params.get("rerank", False)
        self._snippets = params.get("snippets", False)
        self._track_total_hits = params.get("track_total_hits", False)
        self._params = params
        self.infinite = True

        cwd = os.path.dirname(__file__)
        with open(os.path.join(cwd, self._query_file), "r") as file:
            self._queries = json.load(file)
        self._iters = 0

    def partition(self, partition_index, total_partitions):
        return self

    def params(self):
        query_obj = self._queries[self._iters]
        query_text = query_obj["query"]

        if self._rerank:
            query = generate_match_query_with_reranker(
                field=self._field, rerank_field=self._rerank_field, query=query_text, snippets=self._snippets, boost=1
            )
        else:
            query = generate_match_query(field=self._field, query=query_text, boost=1)

        self._iters = (self._iters + 1) % len(self._queries)
        query["track_total_hits"] = self._track_total_hits
        query["size"] = self._size

        return {
            "index": self._index_name,
            "cache": self._cache,
            "body": query,
        }


class RecallParamSource:
    def __init__(self, track, params, **kwargs):
        if len(track.indices) == 1:
            default_index = track.indices[0].name
        else:
            default_index = "_all"

        self._query_file = params.get("query_source", "queries-small.json")
        self._qrels_file = params.get("qrels_source", "qrels-small.tsv")
        self._index_name = params.get("index", default_index)
        self._cache = params.get("cache", False)
        self._size = params.get("size", 10)
        self._field = params.get("field", "content")
        self._rerank_field = params.get("rerank_field", "content")
        self._rerank = params.get("rerank", False)
        self._snippets = params.get("snippets", False)
        self._params = params
        self.infinite = True

        cwd = os.path.dirname(__file__)
        with open(os.path.join(cwd, self._query_file), "r") as file:
            self._queries = json.load(file)
        self._qrels = read_qrels(os.path.join(cwd, self._qrels_file))

    def partition(self, partition_index, total_partitions):
        return self

    def params(self):
        return {
            "index": self._index_name,
            "cache": self._cache,
            "size": self._size,
            "field": self._field,
            "rerank_field": self._rerank_field,
            "rerank": self._rerank,
            "snippets": self._snippets,
            "queries": self._queries,
            "qrels": self._qrels,
        }


class RecallRunner:
    async def __call__(self, es, params):
        results = defaultdict(dict)

        for query_obj in params["queries"]:
            query_id = query_obj["id"]
            query_text = query_obj["query"]

            if params["rerank"]:
                query_body = generate_match_query_with_reranker(
                    field=params["field"], rerank_field=params["rerank_field"], query=query_text, snippets=params["snippets"], boost=1
                )
            else:
                query_body = generate_match_query(field=params["field"], query=query_text, boost=1)

            query_body["size"] = params["size"]

            search_result = await es.search(body=query_body, index=params["index"], request_cache=params["cache"])

            for hit in search_result["hits"]["hits"]:
                doc_id = hit["_source"]["id"]
                score = hit["_score"]
                results[query_id][doc_id] = score

        ndcg_scores = calc_ndcg(params["qrels"], results, [10, 100])

        return {
            "ndcg@10": ndcg_scores["ndcg_cut@10"],
            "ndcg@100": ndcg_scores["ndcg_cut@100"],
        }

    def __repr__(self, *args, **kwargs):
        return "recall"


def register(registry):
    registry.register_param_source("query_param_source", QueryParamsSource)
    registry.register_param_source("recall_param_source", RecallParamSource)
    registry.register_runner("recall", RecallRunner(), async_runner=True)
