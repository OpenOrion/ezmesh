from typing import Sequence
import numpy as np
import colorsys

def generate_color_legend_html(title: str, color_labels: dict[str, list[int]]):
    title = f"<h2>{title}</h2>"
    legend = '<table>'
    for label, color in color_labels.items():
        assert len(color) == 3, "Color must be a list of 3 integers"
        legend += f'<tr><td style="background-color: {to_rgb_str(color)}" width="20"></td><td>{label}</td></tr>'
    legend += '</table>'
    return f'<div style="float: left; padding-right: 50px">{title+legend}</div>'


def generate_rgb_values(n_colors, is_grayscale=False):
    if n_colors == 0:
        return []
    colors=[]
    for i in np.arange(0., 360., 360. / n_colors):
        hue = i/360.
        if is_grayscale:
            min_rgb = 0.5
            rgb = (1 - min_rgb)*hue + min_rgb
            rgb_values = [rgb,rgb,rgb]
        else:
            lightness = (50 + np.random.rand() * 10)/100.
            saturation = (90 + np.random.rand() * 10)/100.
            rgb_values = list(colorsys.hls_to_rgb(hue, lightness, saturation))

        colors.append(rgb_values)


    return colors

def to_rgb_str(color: Sequence[int]):
    return f"rgb({int(color[0]*255)},{int(color[1]*255)},{int(color[2]*255)})"

