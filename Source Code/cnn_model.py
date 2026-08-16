__author__ = 'Rupesh Poudel'
__SourcerepoLink__ = 'https://github.com/rrupeshh/Simple-Sign-Language-Detector'

# Part 1 - Building the CNN
# Importing the Keras libraries and packages
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D        # Fixed: Convolution2D is deprecated
from tensorflow.keras.layers import MaxPooling2D
from tensorflow.keras.layers import Flatten
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras import optimizers

# Initialing the CNN
classifier = Sequential()

# Step 1 - Convolution Layer
# Fixed: Convolution2D -> Conv2D; positional args for kernel_size replaced with tuple
classifier.add(Conv2D(32, (3, 3), input_shape=(64, 64, 3), activation='relu'))

# Step 2 - Pooling
classifier.add(MaxPooling2D(pool_size=(2, 2)))

# Adding second convolution layer
classifier.add(Conv2D(32, (3, 3), activation='relu'))
classifier.add(MaxPooling2D(pool_size=(2, 2)))

# Adding 3rd Convolution Layer
classifier.add(Conv2D(64, (3, 3), activation='relu'))
classifier.add(MaxPooling2D(pool_size=(2, 2)))

# Step 3 - Flattening
classifier.add(Flatten())

# Step 4 - Full Connection
classifier.add(Dense(256, activation='relu'))
classifier.add(Dropout(0.5))
classifier.add(Dense(26, activation='softmax'))

# Compiling The CNN
# Fixed: SGD(lr=...) -> SGD(learning_rate=...) for TF2 compatibility
classifier.compile(
              optimizer=optimizers.SGD(learning_rate=0.01),
              loss='categorical_crossentropy',
              metrics=['accuracy'])

# Part 2 - Fitting the CNN to the image
from tensorflow.keras.preprocessing.image import ImageDataGenerator
train_datagen = ImageDataGenerator(
        rescale=1./255,
        shear_range=0.2,
        zoom_range=0.2,
        horizontal_flip=True)

test_datagen = ImageDataGenerator(rescale=1./255)

training_set = train_datagen.flow_from_directory(
        'Dataset/training_set',
        target_size=(64, 64),
        batch_size=32,
        class_mode='categorical')

test_set = test_datagen.flow_from_directory(
        'Dataset/test_set',
        target_size=(64, 64),
        batch_size=32,
        class_mode='categorical')

# Fixed: fit_generator is removed in TF2; use model.fit() directly
model = classifier.fit(
        training_set,
        steps_per_epoch=800,
        epochs=25,
        validation_data=test_set,
        validation_steps=6500
      )

# Saving the model
classifier.save('ASLModel.h5')

print(model.history.keys())
import matplotlib.pyplot as plt
# summarize history for accuracy
# Fixed: 'acc' -> 'accuracy' (key renamed in TF2)
plt.plot(model.history['accuracy'])
plt.plot(model.history['val_accuracy'])
plt.title('model accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.show()
# summarize history for loss
plt.plot(model.history['loss'])
plt.plot(model.history['val_loss'])
plt.title('model loss')
plt.ylabel('loss')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
plt.show()
