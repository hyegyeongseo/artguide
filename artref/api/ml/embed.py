import open_clip, torch, numpy as np
from config import settings

class Embedder:
    def __init__(self):
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k")
        self.tokenizer = open_clip.get_tokenizer("ViT-B-32")
        self.model.eval()
        self.model_id = settings.embedding_model

    @torch.no_grad()
    def image(self, pil) -> np.ndarray:
        x = self.preprocess(pil).unsqueeze(0)
        v = self.model.encode_image(x)
        return torch.nn.functional.normalize(v, dim=-1)[0].cpu().numpy()

    @torch.no_grad()
    def text(self, s: str) -> np.ndarray:
        v = self.model.encode_text(self.tokenizer([s]))
        return torch.nn.functional.normalize(v, dim=-1)[0].cpu().numpy()

embedder = Embedder()
