# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/006_data.mixed.ipynb (unless otherwise specified).

__all__ = ['MixedDataLoader', 'MixedDataLoaders', 'get_mixed_dls']

# Cell
from ..imports import *

# Cell
# This implementation of a mixed dataloader is based on a great implementation created by Zach Mueller in this fastai thread:
# https://forums.fast.ai/t/combining-tabular-images-in-fastai2-and-should-work-with-almost-any-other-type/73197

from packaging import version
from fastai.data.load import _FakeLoader
from torch.utils.data.dataloader import _MultiProcessingDataLoaderIter, _SingleProcessDataLoaderIter, _DatasetKind
_loaders = (_MultiProcessingDataLoaderIter, _SingleProcessDataLoaderIter)


class MixedDataLoader():
    def __init__(self, *loaders, path='.', shuffle=False, device=None, bs=None):
        "Accepts any number of `DataLoader` and a device"
        self.path = path
        device = ifnone(device, default_device())
        self.device = device
        self.c = None
        bs = ifnone(bs, min([dl.bs for dl in loaders]))
        for i, dl in enumerate(loaders):  # ensure all dls have the same bs
            if hasattr(dl, 'vars'):
                self.vars = dl.vars
            if hasattr(dl, 'len'):
                self.len = dl.len
            dl.bs = bs
            dl.shuffle_fn = self.shuffle_fn
            if self.c is None and hasattr(dl, "c"):
                self.c = dl.c
            if i == 0:
                self.dataset = dl.dataset
            dl.to(device=device)
        self.shuffle = shuffle
        if not self.shuffle:
            self.rng = np.arange(len(self.dataset)).tolist()
        self.loaders = loaders
        self.count = 0
        self.fake_l = _FakeLoader(self, False, 0, 0, 0) if version.parse(
            fastai.__version__) >= version.parse("2.1") else _FakeLoader(self, False, 0, 0)
        if sum([len(dl.dataset) for dl in loaders]) > 0:
            self._get_idxs()  # Do not apply on an empty dataset

    def new(self, *args, **kwargs):
        loaders = [dl.new(*args, **kwargs) for dl in self.loaders]
        return type(self)(*loaders, path=self.path, device=self.device)

    def __len__(self): return len(self.loaders[0])

    def _get_vals(self, x):
        "Checks for duplicates in batches"
        idxs, new_x = [], []
        for i, o in enumerate(x):
            x[i] = o.cpu().numpy().flatten()
        for idx, o in enumerate(x):
            if not self._arrayisin(o, new_x):
                idxs.append(idx)
                new_x.append(o)
        return idxs

    def _get_idxs(self):
        "Get `x` and `y` indices for batches of data"
        self.n_inps = [dl.n_inp for dl in self.loaders]
        self.x_idxs = self._split_idxs(self.n_inps)

        # Identify duplicate targets
        dl_dict = dict(zip(range(0, len(self.loaders)), self.n_inps))
        outs = L([])
        for key, n_inp in dl_dict.items():
            b = next(iter(self.loaders[key]))
            outs += L(b[n_inp:])
        self.y_idxs = self._get_vals(outs)

    def __iter__(self):
        z = zip(*[_loaders[i.fake_l.num_workers == 0](i.fake_l)
                  for i in self.loaders])
        for b in z:
            inps = []
            outs = []
            if self.device is not None:
                b = to_device(b, self.device)
            for batch, dl in zip(b, self.loaders):
                batch = dl.after_batch(batch)
                inps += batch[:dl.n_inp]
                outs += batch[dl.n_inp:]
            inps = tuple([tuple(L(inps)[idx]) if isinstance(idx, list) else inps[idx]
                          for idx in self.x_idxs]) if len(self.x_idxs) > 1 else tuple(L(outs)[self.x_idxs][0])
            outs = tuple(L(outs)[self.y_idxs]) if len(
                self.y_idxs) > 1 else L(outs)[self.y_idxs][0]
            yield inps, outs

    def one_batch(self):
        "Grab one batch of data"
        with self.fake_l.no_multiproc():
            res = first(self)
        if hasattr(self, 'it'):
            delattr(self, 'it')
        return res

    def shuffle_fn(self, idxs):
        "Generate the same idxs for all dls in each batch when shuffled"
        if self.count == 0:
            self.shuffled_idxs = np.random.permutation(idxs)
        self.count += 1
        if self.count == len(self.loaders):
            self.count = 0
        return self.shuffled_idxs

    def show_batch(self):
        "Show a batch of data"
        for dl in self.loaders:
            dl.show_batch()

    def to(self, device): self.device = device

    def _arrayisin(self, arr, arr_list):
        "Checks if `arr` is in `arr_list`"
        for a in arr_list:
            if np.array_equal(arr, a):
                return True
        return False

    def _split_idxs(self, a):
        a_cum = np.array(a).cumsum().tolist()
        b = np.arange(sum(a)).tolist()
        start = 0
        b_ = []
        for i, idx in enumerate(range(len(a))):
            end = a_cum[i]
            b_.append(b[start:end] if end - start > 1 else b[start])
            start = end
        return b_


class MixedDataLoaders(DataLoaders):
    pass

# Cell

def get_mixed_dls(*dls, device=None, shuffle_train=None, shuffle_valid=None, **kwargs):
    _mixed_train_dls = []
    _mixed_valid_dls = []
    for dl in dls:
        _mixed_train_dls.append(dl.train)
        _mixed_valid_dls.append(dl.valid)
        if shuffle_train is None: shuffle_train = dl.train.shuffle
        if shuffle_valid is None: shuffle_valid = dl.valid.shuffle
        if device is None: device = dl.train.device
    mixed_train_dl = MixedDataLoader(*_mixed_train_dls, shuffle=shuffle_train, **kwargs)
    mixed_valid_dl = MixedDataLoader(*_mixed_valid_dls, shuffle=shuffle_valid, **kwargs)
    mixed_dls = MixedDataLoaders(mixed_train_dl, mixed_valid_dl, device=device)
    return mixed_dls