import sys
import os
import datetime

# для запуска из родительской и дочерней папок
sys.path.append('../')
import tensorflow as tf
import random
import matplotlib.pyplot as plt
import numpy as np
import glob
from utils import imageUtils
import re
import itertools

from keras.models import load_model, Sequential
from keras.layers import Dense, Dropout, LSTM, TimeDistributed, Activation, Reshape, Flatten
from keras.optimizers import Adam
from keras.callbacks import ModelCheckpoint, Callback, CSVLogger, TensorBoard,EarlyStopping
from keras.utils.data_utils import Sequence

os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
TIME_TAG = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

SOURCE_FILE_PATH = "dataset/Kapitanskaya_dochka.txt".replace("/", os.sep)
TENSOR_BOARD_FOLDER = "log/tensorboard/{date}/{model}".replace("/", os.sep)
TRAINED_MODEL_PATH = "log/models/{model}.h5".replace("/", os.sep)
TRAIN_LOG_PATH = "log/tensorboard/{date}/{model}/train.log".replace("/", os.sep)
TRAIN_SAMPLES_PATH = "log/tensorboard/{date}/{model}/text_sample_{epoch}.txt".replace("/", os.sep)

chars = set()
chars_inditces = None
inditces_to_char = None
STATEMENT_LEN = 50


def init():
    global chars, chars_inditces, inditces_to_char
    with open(SOURCE_FILE_PATH) as f:
        s = f.read()
        chars.update(list(s.lower()))
    chars_inditces = {c: i for i, c in enumerate(sorted(list(chars)))}
    inditces_to_char = {c: i for i, c in chars_inditces.items()}


def get_one_vector(i, sz):
    res = list(np.zeros(sz))
    res[i] = 1
    return res


def char_to_vector(ch):
    index = chars_inditces[ch.lower()]
    return get_one_vector(index, len(chars))


def vectort_to_chat(vec):
    index = np.argmax(vec)
    return inditces_to_char[index]


def split(text, symbols):
    block = ""
    sentences = []
    for t in text:
        if t in symbols:
            sentences += [block]
            block = ""
        else:
            block += t
    sentences += [block]
    sentences = list(filter(lambda s: len(s) > 0, sentences))
    return sentences


def textGenerator(asVectors=True):
    f = open(SOURCE_FILE_PATH)
    text = f.read()
    f.close()

    sentences = list(filter(lambda s: len(s) > STATEMENT_LEN, split(text, ".,?!\n")))
    while True:
        statement = random.choice(sentences)
        if asVectors:
            x = [[char_to_vector(c) for c in statement[:STATEMENT_LEN]]]
            y = [char_to_vector(statement[-1])]
            yield np.array(x).astype(np.float32), np.array(y).astype(np.float32)
        else:
            x = statement[:STATEMENT_LEN]
            y = statement[-1]
            yield x, y


class CharSampler(Callback):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def logSample(self, epoch):
        newSamplePath = TRAIN_SAMPLES_PATH.format(date=TIME_TAG, model='LSTM', epoch=str(epoch))

        text = textGenerator(asVectors=False).__next__()[0]
        while len(text) < 500 + STATEMENT_LEN:
            x = np.array([char_to_vector(c) for c in text[-STATEMENT_LEN:]]).reshape(1, STATEMENT_LEN, len(chars))
            text += vectort_to_chat(model.predict(x)[0])

        with open(newSamplePath, 'w+') as file:
            file.write(text)

    def on_epoch_end(self, epoch, logs=None):
        self.logSample(epoch)
        pass


if __name__ == "__main__":
    init()
    logTrainPath = TENSOR_BOARD_FOLDER.format(date=TIME_TAG, model='LSTM')
    modelSavePath = TRAINED_MODEL_PATH.format(model="LSTM")
    trainLogPath = TRAIN_LOG_PATH.format(date=TIME_TAG, model='LSTM')
    if not os.path.exists(os.path.dirname(modelSavePath)):
        os.makedirs(os.path.dirname(modelSavePath))
    if not os.path.exists(logTrainPath):
        os.makedirs(logTrainPath)

    if os.path.exists(modelSavePath):
        print("load model %s " % modelSavePath)
        model = load_model(modelSavePath)
    else:
        model = Sequential()
        model.add(LSTM(units=128, input_shape=(STATEMENT_LEN, len(chars),), activation="tanh"))
        model.add(Dropout(0.2))
        model.add(Dense(units=len(chars)))
        model.add(Activation("softmax"))
        model.compile(loss="categorical_crossentropy", optimizer=Adam(), metrics=["accuracy"])
    print(model.summary())

    model.fit_generator(textGenerator(), steps_per_epoch=100, epochs=500, callbacks=[
        TensorBoard(log_dir=logTrainPath,
                    histogram_freq=0,
                    write_graph=True,
                    write_grads=True,
                    write_images=True),
        CSVLogger(trainLogPath),
        CharSampler(model=model),
        ModelCheckpoint(modelSavePath, monitor='loss', verbose=1, save_best_only=True, mode='min')
    ])
    model.save(modelSavePath)