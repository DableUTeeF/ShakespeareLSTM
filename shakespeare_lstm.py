import tensorflow as tf #2.0.0
import numpy as np
import os
import re
import datetime

#Data Settings
MIN_WORD_COUNT = 50

#Training Settings
BATCH_SIZE = 64
BUFFER_SIZE = 10000
EMBEDDING_DIM = 256
EPOCHS = 50
SEQ_LEN = 200
RNN_UNITS = 1024
PATIENCE = 10
TRAIN_PERCENT = 0.9

#File Settings
ROOT = "."
DATA_DIR = os.path.join(ROOT, "shakespeare_data")
CKPT_DIR = os.path.join(ROOT, "checkpoints")
OUTPUT_DIR = os.path.join(ROOT, "lstm_output")
def get_time_for_file():
    return datetime.datetime.now().strftime("_%m.%d.%y-%H:%M:%S")
def get_ckpt_prefix():
    return os.path.join(CKPT_DIR, "ckpt" + get_time_for_file())
PRINT_TO_FILE = True

#Generation Settings
SEED = "a great tale"
NUM_WORDS_GENERATE = 1000
TEMPERATURE = 1.0

text = ""
for file in os.listdir(DATA_DIR):
    if file.endswith(".txt"):
        text += open(os.path.join(DATA_DIR, file)).read().lower()

word_regex = "(?:[A-Za-z\']*(?:(?<!-)-(?!-))*[A-Za-z\']+)+"
punct_regex = r"|\.|\?|!|,|;|:|-|\(|\)|\[|\]|\{|\}|\'|\"|\|\/|<|>| |\t|\n"
regex = word_regex + punct_regex
words = re.findall(regex, text)
word_counts = dict()

for word in words: #create a dict mapping word to count
    word_counts[word] = word_counts.get(word, 0) + 1

word_counts = sorted(list(word_counts.items()), key=lambda i: (-i[1], i[0])) #convert dict to list of tuples sort by count then word

less_than_min = 0
for i in range(len(word_counts) - 1, -1, -1):
    if word_counts[i][1] < MIN_WORD_COUNT:
        less_than_min += word_counts[i][1]
        del word_counts[i]

word_counts.append(("<UNK>", less_than_min))
word_counts.sort(key=lambda i: (-i[1], i[0])) #resort for <UNK>

vocab = [i[0] for i in word_counts] #list of all words
words = [w if w in vocab else "<UNK>" for w in words] #sets words not in vocab to <UNK>

word2int = {w:i for i, w in enumerate(vocab)}
int2word = np.array(vocab)

words_as_ints = np.array([word2int[w] for w in words], dtype=np.int32)

def split_input_target(chunk):
    input_words = chunk[:-1]
    target_words = chunk[1:]
    return input_words, target_words

def build_model(embedding_dim, rnn_units, batch_size):
    return tf.keras.Sequential([
        tf.keras.layers.Embedding(len(vocab), embedding_dim, batch_input_shape=[batch_size, None]),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(rnn_units, return_sequences=True, stateful=True, recurrent_initializer="glorot_uniform"),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(rnn_units, return_sequences=True, stateful=True, recurrent_initializer="glorot_uniform"),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(len(vocab))
    ])

def loss(labels, logits):
    return tf.keras.losses.sparse_categorical_crossentropy(labels, logits, from_logits=True)

def train_model():
    examples_per_epoch = len(words) // SEQ_LEN

    train_size = 0
    while (train_size <= TRAIN_PERCENT * len(words_as_ints) - BATCH_SIZE):
        train_size += BATCH_SIZE

    train_words = words_as_ints[:train_size]
    test_words = words_as_ints[train_size:]

    train_word_dataset = tf.data.Dataset.from_tensor_slices(train_words)
    test_word_dataset = tf.data.Dataset.from_tensor_slices(test_words)

    train_sequences = train_word_dataset.batch(SEQ_LEN + 1, drop_remainder=True)
    test_sequences = test_word_dataset.batch(SEQ_LEN + 1, drop_remainder=True)

    train_dataset = train_sequences.map(split_input_target).shuffle(BUFFER_SIZE).batch(BATCH_SIZE, drop_remainder=True)
    test_dataset = test_sequences.map(split_input_target).shuffle(BUFFER_SIZE).batch(BATCH_SIZE, drop_remainder=True)

    model = build_model(EMBEDDING_DIM, RNN_UNITS, BATCH_SIZE)
    model.summary()

    for input_example_batch, target_example_batch in train_dataset.take(1):
        example_batch_predictions = model(input_example_batch)
        print(example_batch_predictions.shape)

    example_batch_loss = loss(target_example_batch, example_batch_predictions)
    print("Loss: ", example_batch_loss.numpy().mean())

    optimizer = tf.keras.optimizers.Adam()
    model.compile(optimizer=optimizer, loss=loss)
    early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=PATIENCE)

    checkpoint_callback = tf.keras.callbacks.ModelCheckpoint(filepath=get_ckpt_prefix(), save_weights_only=True)

    history = model.fit(train_dataset, epochs=EPOCHS, callbacks=[checkpoint_callback, early_stop], validation_data=test_dataset)

    print("Training stopped due to no improvement after %d epochs" % PATIENCE)

def generate_text(model, seed):
    seed = re.findall(regex, seed)
    input_eval = [word2int[s] for s in seed]
    input_eval = tf.expand_dims(input_eval, 0)
    text_generated = []
    model.reset_states()

    for i in range(NUM_WORDS_GENERATE):
        predictions = model(input_eval)
        predictions = tf.squeeze(predictions, 0)
        predictions = predictions / TEMPERATURE
        predicted_id = tf.random.categorical(predictions, num_samples=1)[-1,0].numpy()
        input_eval = tf.expand_dims([predicted_id], 0)
        text_generated.append(int2word[predicted_id])
    return "".join(text_generated)

def run_model(seed):
    model = build_model(EMBEDDING_DIM, RNN_UNITS, batch_size=1)
    model.load_weights(tf.train.latest_checkpoint(CKPT_DIR))
    model.build(tf.TensorShape([1, None]))

    print("Generating with seed: \"" + seed + "\"\n")
    output = seed + generate_text(model, seed)

    if PRINT_TO_FILE:
        with open(os.path.join(OUTPUT_DIR, "output" + get_time_for_file() + ".txt"), "w") as output_file:
            output_file.write(output)
    else:
        print(output)

run_model(SEED)