import sys, numpy as np, torch, spandrel
sys.argv=['x']; sys.path.insert(0, '.')
import cutout as C
from PIL import Image
m = spandrel.ModelLoader().load_from_file('sr/models/RealESRGAN_x4plus.pth').eval()
torch.set_num_threads(4)
for x in (36, 39, 42):
    rgb = C.get_rgb(x).astype(np.float32) / 255
    t = torch.from_numpy(rgb).permute(2, 0, 1)[None]
    with torch.no_grad(): out = m(t)[0].clamp(0, 1).permute(1, 2, 0).numpy()
    Image.fromarray((out * 255 + .5).astype(np.uint8)).save(f'sr/sr{x}.png'); print(x, rgb.shape, out.shape)
