# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/050_losses.ipynb.

# %% auto 0
__all__ = ['HuberLoss', 'LogCoshLoss', 'MaskedLossWrapper', 'CenterLoss', 'CenterPlusLoss', 'FocalLoss', 'TweedieLoss']

# %% ../nbs/050_losses.ipynb 3
from .imports import *
from fastai.losses import *

# %% ../nbs/050_losses.ipynb 4
## Available in Pytorch 1.9
class HuberLoss(nn.Module):
    """Huber loss 
    
    Creates a criterion that uses a squared term if the absolute
    element-wise error falls below delta and a delta-scaled L1 term otherwise.
    This loss combines advantages of both :class:`L1Loss` and :class:`MSELoss`; the
    delta-scaled L1 region makes the loss less sensitive to outliers than :class:`MSELoss`,
    while the L2 region provides smoothness over :class:`L1Loss` near 0. See
    `Huber loss <https://en.wikipedia.org/wiki/Huber_loss>`_ for more information.
    This loss is equivalent to nn.SmoothL1Loss when delta == 1.
    """
    def __init__(self, reduction='mean', delta=1.0):
        assert reduction in ['mean', 'sum', 'none'], "You must set reduction to 'mean', 'sum' or 'none'"
        self.reduction, self.delta = reduction, delta
        super().__init__()

    def forward(self, input: Tensor, target: Tensor) -> Tensor:
        diff = input - target
        abs_diff = torch.abs(diff)
        mask = abs_diff < self.delta
        loss = torch.cat([(.5*diff[mask]**2), self.delta * (abs_diff[~mask] - (.5 * self.delta))])
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        else: 
            return loss

# %% ../nbs/050_losses.ipynb 5
class LogCoshLoss(nn.Module):
    def __init__(self, reduction='mean', delta=1.0):
        assert reduction in ['mean', 'sum', 'none'], "You must set reduction to 'mean', 'sum' or 'none'"
        self.reduction, self.delta = reduction, delta
        super().__init__()
        
    def forward(self, input: Tensor, target: Tensor) -> Tensor:
        loss = torch.log(torch.cosh(input - target + 1e-12))
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        else: 
            return loss

# %% ../nbs/050_losses.ipynb 7
class MaskedLossWrapper(Module):
    def __init__(self, crit):
        self.loss = crit

    def forward(self, inp, targ):
        inp = inp.flatten(1)
        targ = targ.flatten(1)
        mask = torch.isnan(targ)
        inp, targ = inp[~mask], targ[~mask]
        return self.loss(inp, targ)

# %% ../nbs/050_losses.ipynb 9
class CenterLoss(Module):
    r"""
    Code in Pytorch has been slightly modified from: https://github.com/KaiyangZhou/pytorch-center-loss/blob/master/center_loss.py
    Based on paper: Wen et al. A Discriminative Feature Learning Approach for Deep Face Recognition. ECCV 2016.

    Args:
        c_out (int): number of classes.
        logits_dim (int): dim 1 of the logits. By default same as c_out (for one hot encoded logits)
        
    """
    def __init__(self, c_out, logits_dim=None):
        logits_dim = ifnone(logits_dim, c_out)
        self.c_out, self.logits_dim = c_out, logits_dim
        self.centers = nn.Parameter(torch.randn(c_out, logits_dim))
        self.classes = nn.Parameter(torch.arange(c_out).long(), requires_grad=False)

    def forward(self, x, labels):
        """
        Args:
            x: feature matrix with shape (batch_size, logits_dim).
            labels: ground truth labels with shape (batch_size).
        """
        bs = x.shape[0]
        distmat = torch.pow(x, 2).sum(dim=1, keepdim=True).expand(bs, self.c_out) + \
                  torch.pow(self.centers, 2).sum(dim=1, keepdim=True).expand(self.c_out, bs).T
        distmat = torch.addmm(distmat, x, self.centers.T, beta=1, alpha=-2)

        labels = labels.unsqueeze(1).expand(bs, self.c_out)
        mask = labels.eq(self.classes.expand(bs, self.c_out))

        dist = distmat * mask.float()
        loss = dist.clamp(min=1e-12, max=1e+12).sum() / bs

        return loss


class CenterPlusLoss(Module):
    
    def __init__(self, loss, c_out, λ=1e-2, logits_dim=None):
        self.loss, self.c_out, self.λ = loss, c_out, λ
        self.centerloss = CenterLoss(c_out, logits_dim)
        
    def forward(self, x, labels):
        return self.loss(x, labels) + self.λ * self.centerloss(x, labels)
    def __repr__(self): return f"CenterPlusLoss(loss={self.loss}, c_out={self.c_out}, λ={self.λ})"

# %% ../nbs/050_losses.ipynb 12
class FocalLoss(Module):
    """ Weighted, multiclass focal loss"""

    def __init__(self, alpha:Optional[Tensor]=None, gamma:float=2., reduction:str='mean'):
        """
        Args:
            alpha (Tensor, optional): Weights for each class. Defaults to None.
            gamma (float, optional): A constant, as described in the paper. Defaults to 2.
            reduction (str, optional): 'mean', 'sum' or 'none'. Defaults to 'mean'.
        """
        self.alpha, self.gamma, self.reduction = alpha, gamma, reduction
        self.nll_loss = nn.NLLLoss(weight=alpha, reduction='none')

    def forward(self, x: Tensor, y: Tensor) -> Tensor:

        log_p = F.log_softmax(x, dim=-1)
        pt = log_p[torch.arange(len(x)), y].exp()
        ce = self.nll_loss(log_p, y)
        loss = (1 - pt) ** self.gamma * ce

        if self.reduction == 'mean':
            loss = loss.mean()
        elif self.reduction == 'sum':
            loss = loss.sum()
        return loss

# %% ../nbs/050_losses.ipynb 14
class TweedieLoss(Module):
    def __init__(self, p=1.5, eps=1e-8):
        """
        Tweedie loss as calculated in LightGBM
        Args:
            p: tweedie variance power (1 < p < 2)
            eps: small number to avoid log(zero).
        """
        assert 1 < p < 2, "make sure 1 < p < 2" 
        self.p, self.eps = p, eps

    def forward(self, inp, targ):
        "Poisson and compound Poisson distribution, targ >= 0, inp > 0"
        inp = inp.flatten()
        targ = targ.flatten()
        torch.clamp_min_(inp, self.eps)
        a = targ * torch.exp((1 - self.p) * torch.log(inp)) / (1 - self.p)
        b = torch.exp((2 - self.p) * torch.log(inp)) / (2 - self.p)
        loss = -a + b
        return loss.mean()
