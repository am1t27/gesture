"""
model_compat.py
Pure numpy/h5py inference engine for ASLModel.h5

Works on Python 3.13 with NO TensorFlow or Keras dependency.
H5 structure confirmed:
  model_weights/conv2d_1/conv2d_1/{kernel:0, bias:0}  shape=(3,3,3,32)
  model_weights/conv2d_2/conv2d_2/{kernel:0, bias:0}  shape=(3,3,32,32)
  model_weights/dense_1/dense_1/{kernel:0, bias:0}    shape=(6272,256)
  model_weights/dense_2/dense_2/{kernel:0, bias:0}    shape=(256,26)
"""
import numpy as np
import h5py
import os


# ─── Activations ─────────────────────────────────────────────────────────────

def relu(x):
    return np.maximum(0.0, x)

def softmax(x):
    e = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


# ─── Layers ──────────────────────────────────────────────────────────────────

def conv2d_forward(x, kernel, bias):
    """
    Vectorized (im2col) 'valid' convolution — numerically equivalent to the
    original triple-nested-loop version, but ~300-500x faster since the
    inner work is done as one batched matmul instead of per-pixel Python loops.

    x:      (N, H, W, C_in)
    kernel: (kH, kW, C_in, C_out)
    bias:   (C_out,)
    returns (N, H-kH+1, W-kW+1, C_out)
    """
    N, H, W, C_in = x.shape
    kH, kW, _, C_out = kernel.shape

    # (N, oH, oW, C_in, kH, kW) -> reorder to (N, oH, oW, kH, kW, C_in)
    windows = np.lib.stride_tricks.sliding_window_view(x, (kH, kW), axis=(1, 2))
    windows = np.transpose(windows, (0, 1, 2, 4, 5, 3))
    oH, oW = windows.shape[1], windows.shape[2]

    patches = windows.reshape(N * oH * oW, kH * kW * C_in)
    k2 = kernel.reshape(kH * kW * C_in, C_out)
    out = patches @ k2 + bias
    return out.reshape(N, oH, oW, C_out).astype(np.float32)

def maxpool2d_forward(x, size=2):
    """Vectorized non-overlapping max-pool (stride == size)."""
    N, H, W, C = x.shape
    oH, oW = H // size, W // size
    xt = x[:, :oH * size, :oW * size, :]
    xt = xt.reshape(N, oH, size, oW, size, C)
    return xt.max(axis=(2, 4))

def dense_forward(x, kernel, bias):
    return x @ kernel + bias


# ─── Model ───────────────────────────────────────────────────────────────────

class ASLModel:
    def __init__(self, W):
        self.W = W  # dict: layer_key -> {'kernel': ndarray, 'bias': ndarray}

    def predict(self, x):
        """
        x: (N, 64, 64, 3)  — values as float32 0-255 or 0-1 (we handle both)
        returns: (N, 26) softmax probabilities
        """
        x = x.astype(np.float32)
        if x.max() > 1.0:
            x = x / 255.0

        # Conv block 1
        x = relu(conv2d_forward(x, self.W['conv2d_1']['kernel'], self.W['conv2d_1']['bias']))
        x = maxpool2d_forward(x, 2)

        # Conv block 2
        x = relu(conv2d_forward(x, self.W['conv2d_2']['kernel'], self.W['conv2d_2']['bias']))
        x = maxpool2d_forward(x, 2)

        # Flatten
        x = x.reshape(x.shape[0], -1)

        # Dense 1
        x = relu(dense_forward(x, self.W['dense_1']['kernel'], self.W['dense_1']['bias']))

        # Dense 2 (output)
        x = softmax(dense_forward(x, self.W['dense_2']['kernel'], self.W['dense_2']['bias']))

        return x


# ─── Loader ──────────────────────────────────────────────────────────────────

def load_asl_model(model_path: str) -> ASLModel:
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    # Confirmed H5 path: model_weights/<layer>/<layer>/kernel:0
    layer_names = ['conv2d_1', 'conv2d_2', 'dense_1', 'dense_2']
    W = {}

    with h5py.File(model_path, 'r') as f:
        mw = f['model_weights']
        for name in layer_names:
            group = mw[name][name]   # double-nested: mw/conv2d_1/conv2d_1/
            W[name] = {
                'kernel': np.array(group['kernel:0'], dtype=np.float32),
                'bias':   np.array(group['bias:0'],   dtype=np.float32),
            }

    return ASLModel(W)


# ─── Image helpers ───────────────────────────────────────────────────────────

def load_img(path, target_size=None):
    from PIL import Image
    img = Image.open(path).convert('RGB')
    if target_size:
        img = img.resize((target_size[1], target_size[0]))
    return img

def img_to_array(img):
    return np.array(img, dtype=np.float32)
