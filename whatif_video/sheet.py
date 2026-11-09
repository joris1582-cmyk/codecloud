import sys, glob
from PIL import Image
part = sys.argv[1]; out = sys.argv[2]
fs = sorted(glob.glob(f'preview2/vertical_p{part}_*.jpg'), key=lambda f: float(f.split('_')[-1][:-4]))
if len(sys.argv) > 3: fs = [f for f in fs if f.split('_')[-1][:-4] in sys.argv[3:]]
ims = [Image.open(f).resize((270, 480)) for f in fs]
m = Image.new('RGB', (270 * len(ims), 480)); [m.paste(im, (i * 270, 0)) for i, im in enumerate(ims)]; m.save(out)
