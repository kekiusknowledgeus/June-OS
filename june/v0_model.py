"""June V0 neural network architecture, matching the original training checkpoint."""

import torch
from torch import nn
from torch.nn import functional as F


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model: int, n_head: int, dropout: float):
        super().__init__()
        self.n_head = n_head
        self.dropout = dropout
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.proj = nn.Linear(d_model, d_model)

    def forward(self, x):
        b, t, c = x.shape
        q, k, v = (self.qkv(x)
                   .view(b, t, 3, self.n_head, c // self.n_head)
                   .permute(2, 0, 3, 1, 4)
                   .unbind(0))
        y = F.scaled_dot_product_attention(
            q, k, v,
            is_causal=True,
            dropout_p=self.dropout if self.training else 0.0,
        )
        return self.proj(y.transpose(1, 2).contiguous().view(b, t, c))


class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, n_head: int, dropout: float):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_head, dropout)
        self.ln2 = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, 4 * d_model),
            nn.GELU(),
            nn.Linear(4 * d_model, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        return x + self.ffn(self.ln2(x))


class JuneV0(nn.Module):
    def __init__(self, vocab_size: int, block_size: int, d_model: int,
                 n_head: int, n_layer: int, dropout: float):
        super().__init__()
        self.block_size = block_size
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.position_embedding = nn.Embedding(block_size, d_model)
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.Sequential(*[
            TransformerBlock(d_model, n_head, dropout) for _ in range(n_layer)
        ])
        self.ln_final = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, idx):
        b, t = idx.shape
        if t > self.block_size:
            raise ValueError('Input exceeds model context length')
        x = self.token_embedding(idx) + self.position_embedding(torch.arange(t, device=idx.device))
        x = self.blocks(self.drop(x))
        return self.lm_head(self.ln_final(x))

    @torch.inference_mode()
    def generate(self, idx, max_new_tokens=100, temperature=0.8, top_k=20):
        self.eval()
        for _ in range(max_new_tokens):
            context = idx[:, -self.block_size:]
            logits = self(context)[:, -1, :] / max(temperature, 1e-5)
            if top_k is not None:
                values, _ = torch.topk(logits, min(top_k, logits.shape[-1]))
                logits[logits < values[:, [-1]]] = -float('inf')
            next_idx = torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)
            idx = torch.cat((idx, next_idx), dim=1)
        return idx
