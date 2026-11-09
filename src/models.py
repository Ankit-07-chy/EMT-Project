"""Model zoo: the model families suggested by the literature.

| Family | Source in the reading list | Implementation |
|---|---|---|
| RF, ET  | brief (Random Forest / Extra Trees)                        | scikit-learn |
| KNN     | Slimani et al. 2024/2025: KNN beat a 1D-CNN at localisation | scikit-learn, scaled inputs |
| MLP     | Smail et al. 2011: neural-network inverse model on TDR       | scikit-learn MLP, scaled inputs and targets |
| CNN     | Scarpetta et al. 2021 (Zenodo data), Slimani 2024: 1D-CNN    | PyTorch 1-D CNN on the raw trace (Method A only) |

Every model has the scikit-learn interface (fit / predict / predict_proba), so
training, evaluation, the dashboard and joblib saving treat them all the same.
"""
from __future__ import annotations

import os
import time

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import (ExtraTreesClassifier, ExtraTreesRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FAMILIES = ("RF", "ET", "KNN", "MLP", "CNN")
FAMILY_NAME = {"RF": "Random Forest", "ET": "Extra Trees", "KNN": "k-nearest neighbours",
               "MLP": "MLP neural network", "CNN": "1-D CNN"}
# which inputs each family is trained on (a CNN needs the raw sequence)
FAMILY_METHODS = {"RF": ("A", "B"), "ET": ("A", "B"), "KNN": ("A", "B"),
                  "MLP": ("A", "B"), "CNN": ("A",)}
SUPPORTS_WEIGHT = {"RF", "ET", "CNN"}


def set_threads(model, n_jobs: int):
    """Set every ``n_jobs`` inside a model (pipelines included). One trace at a
    time (dashboard, live checks) is about 4x faster single-threaded: starting a
    thread pool costs more than predicting one row."""
    try:
        keys = [k for k in model.get_params(deep=True) if k == "n_jobs" or k.endswith("__n_jobs")]
    except Exception:
        return model
    if keys:
        model.set_params(**{k: n_jobs for k in keys})
    return model


def make_model(task: str, family: str, params: dict, n_estimators: int = 100, seed: int = 0):
    p = dict(params)
    if family in ("RF", "ET"):
        cls = {("reg", "RF"): RandomForestRegressor, ("cls", "RF"): RandomForestClassifier,
               ("reg", "ET"): ExtraTreesRegressor, ("cls", "ET"): ExtraTreesClassifier}[(task, family)]
        return cls(n_estimators=n_estimators, n_jobs=-1, random_state=seed, **p)
    if family == "KNN":
        est = (KNeighborsRegressor if task == "reg" else KNeighborsClassifier)(n_jobs=-1, **p)
        return make_pipeline(StandardScaler(), est)
    if family == "MLP":
        kw = dict(early_stopping=True, max_iter=300, n_iter_no_change=12, random_state=seed)
        kw.update(p)
        if task == "reg":
            return TransformedTargetRegressor(make_pipeline(StandardScaler(), MLPRegressor(**kw)),
                                              transformer=StandardScaler())
        return make_pipeline(StandardScaler(), MLPClassifier(**kw))
    if family == "CNN":
        return CNN1D(task=task, seed=seed, **p)
    raise ValueError(family)


# ---------------------------------------------------------------- 1-D CNN
def _torch():
    import torch
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    return torch


def _build_net(torch, length: int, channels, kernel: int, n_out: int, dropout: float):
    nn = torch.nn
    layers, c_in, L = [], 1, length
    for c in channels:
        layers += [nn.Conv1d(c_in, c, kernel, padding=kernel // 2), nn.BatchNorm1d(c), nn.ReLU(),
                   nn.Conv1d(c, c, kernel, padding=kernel // 2), nn.BatchNorm1d(c), nn.ReLU(),
                   nn.MaxPool1d(2)]
        c_in, L = c, L // 2
    # flatten keeps *where* along the trace a feature was found: position is the target
    layers += [nn.Flatten(), nn.Dropout(dropout), nn.Linear(c_in * L, 128), nn.ReLU(),
               nn.Dropout(dropout), nn.Linear(128, n_out)]
    return nn.Sequential(*layers)


class CNN1D(BaseEstimator):
    """1-D convolutional network on the raw trace (scikit-learn style).

    Large arrays (e.g. a memory-mapped 800k x 1024 dataset) are streamed in
    contiguous chunks, so the whole set never has to sit in RAM.
    """

    def __init__(self, task="reg", channels=(16, 32, 64, 64), kernel=7, dropout=0.2,
                 epochs=40, batch=256, lr=2e-3, weight_decay=1e-4, patience=6,
                 val_frac=0.1, chunk=65536, max_minutes=None, seed=0, verbose=False):
        self.task, self.channels, self.kernel, self.dropout = task, channels, kernel, dropout
        self.epochs, self.batch, self.lr, self.weight_decay = epochs, batch, lr, weight_decay
        self.patience, self.val_frac, self.chunk = patience, val_frac, chunk
        self.max_minutes, self.seed, self.verbose = max_minutes, seed, verbose

    # sklearn tags
    @property
    def _estimator_type(self):
        return "regressor" if self.task == "reg" else "classifier"

    def _xt(self, torch, X):
        x = (np.asarray(X, np.float32) - self.x_mean_) / self.x_std_
        return torch.from_numpy(x).unsqueeze(1)

    def fit(self, X, y, sample_weight=None):
        torch = _torch()
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        n, L = X.shape
        y = np.asarray(y)
        sw = np.ones(n, np.float32) if sample_weight is None else np.asarray(sample_weight, np.float32)
        # input scaling from a sample of rows
        probe = np.asarray(X[rng.choice(n, min(n, 20000), replace=False)], np.float32)
        self.x_mean_, self.x_std_ = float(probe.mean()), float(probe.std() + 1e-8)
        if self.task == "reg":
            self.y_mean_, self.y_std_ = float(y.mean()), float(y.std() + 1e-8)
            yt = ((y - self.y_mean_) / self.y_std_).astype(np.float32)
            n_out = 1
        else:
            self.classes_, yt = np.unique(y, return_inverse=True)
            yt = yt.astype(np.int64)
            n_out = len(self.classes_)
        # validation split: random rows for in-RAM data, the last block for memmaps
        streamed = isinstance(X, np.memmap) or n > 300_000
        n_val = max(1, int(n * self.val_frac))
        if streamed:
            tr_idx, va_idx = np.arange(n - n_val), np.arange(n - n_val, n)
        else:
            perm = rng.permutation(n)
            tr_idx, va_idx = np.sort(perm[n_val:]), np.sort(perm[:n_val])
        net = _build_net(torch, L, self.channels, self.kernel, n_out, self.dropout)
        opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=max(1, self.patience // 2))
        Xv = self._xt(torch, X[va_idx])
        yv = torch.from_numpy(yt[va_idx])
        best, best_state, bad = np.inf, None, 0
        t0 = time.time()
        self.history_ = []
        for ep in range(self.epochs):
            net.train()
            tot, cnt = 0.0, 0
            for xb, yb, wb in self._batches(torch, X, yt, sw, tr_idx, rng, streamed):
                opt.zero_grad()
                out = net(xb)
                if self.task == "reg":
                    loss_v = torch.nn.functional.smooth_l1_loss(out.squeeze(1), yb, reduction="none", beta=0.5)
                else:
                    loss_v = torch.nn.functional.cross_entropy(out, yb, reduction="none")
                loss = (loss_v * wb).sum() / wb.sum()
                loss.backward()
                opt.step()
                tot += float(loss.detach()) * len(xb)
                cnt += len(xb)
            vloss = self._val_loss(torch, net, Xv, yv)
            sched.step(vloss)
            self.history_.append((ep, tot / max(cnt, 1), vloss))
            if self.verbose:
                print(f"    CNN epoch {ep + 1:3d} train {tot / max(cnt, 1):.4f} val {vloss:.4f} ({time.time() - t0:.0f}s)")
            if vloss < best - 1e-5:
                best, bad = vloss, 0
                best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
            if self.max_minutes and time.time() - t0 > 60 * self.max_minutes:
                break
        net.load_state_dict(best_state)
        net.eval()
        self.net_ = net
        self.n_features_in_ = L
        return self

    def _batches(self, torch, X, yt, sw, idx, rng, streamed):
        if streamed:   # contiguous chunks in random order, shuffled inside each chunk
            starts = np.arange(0, len(idx), self.chunk)
            for s in rng.permutation(starts):
                block = idx[s:s + self.chunk]
                Xc = np.asarray(X[block[0]:block[-1] + 1], np.float32)
                p = rng.permutation(len(block))
                for b in range(0, len(block), self.batch):
                    j = p[b:b + self.batch]
                    yield (self._xt(torch, Xc[j]), torch.from_numpy(yt[block[j]]),
                           torch.from_numpy(sw[block[j]]))
        else:
            p = rng.permutation(idx)
            for b in range(0, len(p), self.batch):
                j = np.sort(p[b:b + self.batch])
                yield self._xt(torch, X[j]), torch.from_numpy(yt[j]), torch.from_numpy(sw[j])

    def _val_loss(self, torch, net, Xv, yv):
        net.eval()
        with torch.no_grad():
            outs = [net(Xv[i:i + 2048]) for i in range(0, len(Xv), 2048)]
            out = torch.cat(outs)
            if self.task == "reg":
                return float(torch.nn.functional.smooth_l1_loss(out.squeeze(1), yv, beta=0.5))
            return float(torch.nn.functional.cross_entropy(out, yv))

    def _forward(self, X):
        torch = _torch()
        self.net_.eval()
        outs = []
        with torch.no_grad():
            for i in range(0, len(X), 4096):
                outs.append(self.net_(self._xt(torch, X[i:i + 4096])).numpy())
        return np.concatenate(outs) if outs else np.zeros((0, 1))

    def predict(self, X):
        out = self._forward(X)
        if self.task == "reg":
            return out[:, 0] * self.y_std_ + self.y_mean_
        return self.classes_[out.argmax(1)]

    def predict_proba(self, X):
        out = self._forward(X)
        e = np.exp(out - out.max(1, keepdims=True))
        return e / e.sum(1, keepdims=True)
