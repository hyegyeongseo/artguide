"""ml/embed.py — CLIP 임베더. 모델은 EMBEDDING_MODEL(env)로 결정, 차원은 모델이 결정.

EMBEDDING_MODEL 형식:  "open_clip:<arch>:<pretrained>"
  예) open_clip:ViT-L-14:openai          # OpenAI CLIP ViT-L/14 = clip-vit-large-patch14 (768) — Spring과 동일 공간
      open_clip:ViT-B-32:laion2b_s34b_b79k  # 구버전(512) — 로컬 단독 테스트용으로 되돌릴 때

미설정/파싱 실패 시 안전 기본값 = ViT-L-14 / openai (768). 모델만 바꾸면 코드 수정 불필요.
self.dim 은 실제 출력 차원(qdrant 컬렉션 생성·검증에 사용 — 하드코딩 제거).
"""
import open_clip, torch, numpy as np
from config import settings

_DEFAULT = ("ViT-L-14", "openai")  # Spring(clip-vit-large-patch14, 768)과 같은 가중치


def _parse_model_id(model_id: str):
    """'open_clip:<arch>:<pretrained>' → (arch, pretrained). 'open_clip:' 접두는 선택."""
    if not model_id:
        return _DEFAULT
    parts = [p.strip() for p in model_id.split(":")]
    if parts and parts[0].lower() in ("open_clip", "openclip"):
        parts = parts[1:]
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return _DEFAULT


class Embedder:
    def __init__(self):
        self.model_id = settings.embedding_model or "open_clip:ViT-L-14:openai"
        arch, pretrained = _parse_model_id(self.model_id)
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            arch, pretrained=pretrained)
        self.tokenizer = open_clip.get_tokenizer(arch)
        self.model.eval()
        # 실제 임베딩 차원(모델이 결정). 컬렉션 size·검증에 사용.
        self.dim = int(self.text("dimension probe").shape[0])

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
