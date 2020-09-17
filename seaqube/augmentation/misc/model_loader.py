import os.path as Path
from gensim.models._fasttext_bin import load
import gensim.downloader as api

from seaqube.augmentation.misc.embedding_model_wrapper import PreTrainedGensimEN
from seaqube.package_config import package_path, log


def load_fasttext_en_pretrained():
    log.info("Load FT Model")
    path = Path.join(package_path, 'augmentation', 'data', 'fasttext_en', 'cc.en.300.bin')

    if not Path.isfile(path):
        raise ValueError("Fast Text Pretrained Model is not available, please run: download('fasttext-en-pretrained')")

    with open(path, 'rb') as fin:
        return PreTrainedGensimEN(load(fin))


def load_word2vec_en_pretrained():
    log.info("Load W2V Model")
    model = api.load("glove-wiki-gigaword-50")
    return PreTrainedGensimEN(model)