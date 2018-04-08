import requests, re
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw
from itertools import product

def get_template(query):
    res = requests.get('https://imgflip.com/memesearch', params={'q': query})
    url = re.findall(r'(//i\.imgflip\.com/[^\/]+\.(?:jpe?g|png))', res.text)[0]
    url = 'http:' + url
    img = Image.open(BytesIO(requests.get(url).content))
    return img

def get_lines(w, wf, words):
    if not words: return ['']
    lines = []
    while words:
        lines.append([words[0]])
        words.pop(0)
        while words and wf(' '.join(lines[-1] + [words[0]])) < w:
            lines[-1].append(words[0])
            words.pop(0)
    return list(map(' '.join, lines))

def draw_outlined_text(draw, xy, outline_size=1, outline_color='black', text_color='white', **kwargs):
    changes = product([-outline_size, 0, outline_size], repeat=2)
    for change in changes:
        draw.text((xy[0] + change[0], xy[1] + change[1]), fill=outline_color, **kwargs)
    draw.text(xy, fill=text_color, **kwargs)

def add_text(img, top, bottom):
    font = ImageFont.truetype('impact', 40)
    w, h = img.size
    wf = lambda x: font.getsize(x)[0]
    top_lines = get_lines(w, wf, top.split())
    bottom_lines = get_lines(w, wf, bottom.split())
    # outline code here
    draw = ImageDraw.Draw(img)
    top = '\n'.join(top_lines)
    bottom = '\n'.join(bottom_lines)
    top_size = draw.textsize(top, font=font)
    top_offset = ((w - top_size[0]) / 2, 0)
    bottom_size = draw.textsize(top, font=font)
    bottom_offset = ((w - bottom_size[0]) / 2, h - bottom_size[1])

    draw_outlined_text(draw, top_offset, text=top, font=font, align='center')
    draw_outlined_text(draw, bottom_offset, text=bottom, font=font, align='center')
    return img

def make_meme(query, top, bottom):
    img = get_template(query)
    dim = max(img.size)
    if dim > 600:
        scale = 600.0 / dim
        img = img.resize(tuple(map(lambda x: int(x*scale), img.size)))
    img = add_text(img, top or '', bottom or '')
    img.save('test.jpg')
    return img