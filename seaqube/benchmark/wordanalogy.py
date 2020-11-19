'''
Copyright (c) 2020 by Benjamin Manns
This file is part of the Semantic Quality Benchmark for Word Embeddings Tool in Python (SeaQuBe).
:author: Benjamin Manns
'''
import gc
import itertools

from pandas import read_csv
import numpy as np
from progressbar import progressbar, ProgressBar
from sklearn.metrics import pairwise_distances

from seaqube.benchmark._benchmark import DataSetBasedWordEmbeddingBenchmark, get_shipped_test_set_path, \
    get_list_of_shipped_test_sets, BenchmarkScore
from seaqube.nlp.types import SeaQuBeWordEmbeddingsModel
from seaqube.package_config import log
from seaqube.tools.math import cosine
from seaqube.tools.umproc import ForEach


class WordAnalogyBenchmark(DataSetBasedWordEmbeddingBenchmark):
    def __init__(self, test_set, method="3CosAdd", multiprocessing: bool = False, max_cpus=None):
        self.method = method
        self.max_cpus = max_cpus
        self.multiprocessing = multiprocessing
        super(WordAnalogyBenchmark, self).__init__(test_set)

    def method_name(self):
        return "wordanalogy"

    def _load_shipped_test_set(self, test_set):
        """"

        """
        path = get_shipped_test_set_path("word-analogy", test_set)
        return read_csv(path)

    def available_test_sets(self):
        return get_list_of_shipped_test_sets("word-analogy")

    def most_similar(self, calculated_vector, model: SeaQuBeWordEmbeddingsModel, topn=10):
        vocab_len = len(model.vocabs())

        distances = np.array([np.linalg.norm(calculated_vector - model.matrix()[i]) for i in range(vocab_len)])
        found_indecies = np.array(distances).argsort()[0:topn]

        return list(zip(np.array(model.vocabs())[found_indecies], distances[found_indecies]))

    def _nearest_neighbors(self, a, b, c, model: SeaQuBeWordEmbeddingsModel, exclude=[]):

        """
        See https://github.com/kudkudak/word-embeddings-benchmarks/blob/master/web/embedding.py
        Find nearest neighbor of given word
        Parameters
        ----------
          word: string or vector
            Query word or vector.
          k: int, default: 1
            Number of nearest neighbours to return.
          metric: string, default: 'cosine'
            Metric to use.
          exclude: list, default: []
            Words to omit in answer
        Returns
        -------
          n: list
            Nearest neighbors.
        """
        k = 10
        # exclude = []
        metric = "cosine"

        word2index = {word: i for i, word in enumerate(model.wv.vocabs)}
        index2word = {i: word for i, word in enumerate(model.wv.vocabs)}

        # if isinstance(word, str):
        #     assert word in vocabs, "Word not found in the vocabulary"
        #     v = w2v.wv[word]
        # else:  # otherwise it is a vector
        #     v = word
        v = a + b - c

        D = pairwise_distances(model.wv.matrix, v.reshape(1, -1), metric=metric)

        for w in exclude:
            D[word2index[w]] = D.max()

        return [index2word[id] for id in D.argsort(axis=0).flatten()[0:k]]

    def _3_cos_add(self, a, b, c, model: SeaQuBeWordEmbeddingsModel, exclude=[]):
        vocab_len = model.matrix().shape[0]
        res = []
        for i in range(vocab_len):
            d = model.matrix()[i]
            res.append(cosine(d, c) - cosine(d, a) + cosine(d, b))

        sorted_zip = list(zip(
            np.array(model.vocabs())[np.argsort(res)[::-1]],  # [::-1] is for maximizing
            np.sort(res)[::-1]
        ))

        sorted_top = sorted_zip[0:10]
        del sorted_zip
        gc.collect()
        return sorted_top

    def _vector_calc(self, a, b, c, model: SeaQuBeWordEmbeddingsModel, exclude=[]):
        calculated_wv = a - b + c
        return self.most_similar(calculated_wv, model)

    def _pair_dir(self, a, b, c, model: SeaQuBeWordEmbeddingsModel, exclude=[]):
        vocab_len = model.matrix().shape[0]
        res = []
        for i in range(vocab_len):
            d = model.matrix()[i]
            res.append(cosine(d - c, b - a))

        return list(zip(
            np.array(model.vocabs())[np.argsort(res)[::-1]],  # [::-1] is for maximizing
            np.sort(res)[::-1]
        ))[0:10]

    def _space_evolution(self, a, b, c, model: SeaQuBeWordEmbeddingsModel, exclude=[]):
        a_h = a / np.linalg.norm(a)
        b_h = b / np.linalg.norm(b)
        c_h = c / np.linalg.norm(c)

        return self._3_cos_add(a_h, b_h, c_h, model)

    def apply_on_testset_line(self, row):
        log.info(f"WordAnalogy of these relation:{row.word1}:{row.word2}::{row.word3}:?")

        log.info(f"WordAnalogy: target={row.target}")
        detected_targets = self.measure_method(self.model.wv[row.word1], self.model.wv[row.word2],
                                               self.model.wv[row.word3], self.model,
                                               exclude=[row.word1, row.word2, row.word3])

        log.info(f"WordAnalogy: detected_targets={detected_targets}")

        word = detected_targets[0][0]

        del detected_targets
        return int(word == row.target)

    def __call__(self, model: SeaQuBeWordEmbeddingsModel) -> BenchmarkScore:
        correct_hits = 0

        if self.method == "3CosAdd":
            self.measure_method = self._3_cos_add
        elif self.method == 'VectorCalc':
            self.measure_method = self._vector_calc
        elif self.method == 'PairDir':
            self.measure_method = self._pair_dir
        elif self.method == 'SpaceEvolution':
            self.measure_method = self._space_evolution
        elif self.method == "NearestNeighbors":
            self.measure_method = self._nearest_neighbors
        else:
            raise ValueError(
                f"Argument `method` must be in one of [3CosAdd, VectorCalc, PairDir, SpaceEvolution, NearestNeighbors]")

        self.model = model

        # first filter dataset
        # all words need to be in the vocab list, otherwise it makes no sense
        filtered_rows = []
        for rowitem in progressbar(self.test_set.iterrows(), max_value=len(self.test_set)):
            _, row = rowitem

            if row.word1 in self.model.vocabs() and row.word2 in self.model.vocabs() and row.word3 in self.model.vocabs() and row.target in self.model.vocabs():
                filtered_rows.append(row)

        # then use filtered row for hard work
        prg = ProgressBar(max_value=len(filtered_rows))
        if self.multiprocessing:
            multi_wrapper = ForEach(self.apply_on_testset_line, max_cpus=self.max_cpus)
        else:
            def multi_wrapper(rows):
                for doc in rows:
                    yield self.apply_on_testset_line(doc)

        for correct_flag in multi_wrapper(filtered_rows):
            correct_hits += correct_flag
            prg.update(prg.value + 1)

        considered_lines = len(filtered_rows)

        if considered_lines == 0:
            return BenchmarkScore(0.0)

        return BenchmarkScore(correct_hits / considered_lines, {'matched_words': considered_lines})
