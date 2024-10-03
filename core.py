import numpy as np
import time
import bpy
import os

from . import web
from . import settings
from . import pro

# TODO: 16/32 bit float images
# TODO: image sequence support
# TODO: UDIM TILES
# TODO: persistent data storage and file loading handler
# TODO: better packed image handling


class ImageInfo:
    def __init__(self, image, path):
        self.image = image
        self.original_path = path
        self.optimized_path = None
        self.sharpness_factor = 100
        self.color_factor = 100
        self.alpha_factor = 100
        self.range_factor = 0
        self.size_original_mb = 0
        self.size_optimized_mb = 0
        self.optimized_resolution = None
        self.optimized_depth = None
        self.read_as_half_precision = False


def is_optimized(image_list):
    """Check if any images have been optimized."""
    return any([i.optimized_path is not None for i in image_list])


def tally_packed(img_list):
    """Tally the number of packed images in the list."""
    packed_count = 0
    for img_info in img_list:
        if img_info.image.packed_file:
            packed_count += 1
    return packed_count


def tally_sizes(image_list):
    """calculate and return some stats"""
    total_original = 0
    total_optimized = 0

    for img_info in image_list:
        total_original += img_info.size_original_mb
        total_optimized += img_info.size_optimized_mb

    num_of_changes = len([i for i in image_list if i.size_original_mb > i.size_optimized_mb])
    return (
        total_original,
        total_optimized,
        total_original - total_optimized,
        num_of_changes,
    )


def analyze_sharpness(pixel_data):
    # pixel_data is expected to be a numpy array with shape (h, w, 4)
    max_gnorm = 0

    if settings.HYPERSPEED:
        # downsize pixel_data by half to speed things up
        pixel_data = pixel_data[::2, ::2, :]

    # instead of using gradient, potentially look into doing a successive resizing and comparing with original
    for channel in range(4):  # Iterate over R, G, B, A channels
        gx, gy = np.gradient(pixel_data[:, :, channel])
        gnorm = np.sqrt(gx**2 + gy**2)
        max_gnorm = max(max_gnorm, np.max(gnorm))

    return max_gnorm * 10


def analyze_rgba(pixel_data):
    # pixel_data is expected to be a numpy array with shape (h, w, 4)
    # Extract the RGB channels

    if settings.HYPERSPEED:
        # downsize pixel_data by half to speed things up
        pixel_data = pixel_data[::2, ::2, :]

    rgb = pixel_data[:, :, :3]
    alpha = pixel_data[:, :, 3]

    # Calculate the absolute differences between R, G, and B channels
    diff_rg = np.abs(rgb[..., 0] - rgb[..., 1])
    diff_rb = np.abs(rgb[..., 0] - rgb[..., 2])
    diff_gb = np.abs(rgb[..., 1] - rgb[..., 2])

    color_factor = np.max(diff_rg) + np.max(diff_rb) + np.max(diff_gb)
    alpha_factor = not np.all(alpha == 1.0)

    # tally up the unique colors
    # unique_colors = np.unique(pixel_data.reshape(-1, 4), axis=0)
    # range_factor = len(unique_colors)
    range_factor = 0

    return color_factor, alpha_factor, range_factor


def optimize_size(img_info, settings, execute=False):
    smart_resize = float(settings["smart_resize"])

    if img_info.sharpness_factor < 0.1 * smart_resize:
        img_info.size_optimized_mb /= 64
        img_info.optimized_resolution = [img_info.image.size[0] // 8, img_info.image.size[1] // 8]
    elif img_info.sharpness_factor < 0.15 * smart_resize:
        img_info.size_optimized_mb /= 16
        img_info.optimized_resolution = [img_info.image.size[0] // 4, img_info.image.size[1] // 4]
    elif img_info.sharpness_factor < 0.3 * smart_resize:
        img_info.size_optimized_mb /= 4
        img_info.optimized_resolution = [img_info.image.size[0] // 2, img_info.image.size[1] // 2]
    return img_info


def optimize_depth(img_info, settings, execute=False):
    convert_greyscale = float(settings["convert_greyscale"])
    optimize_float = float(settings["optimize_float"])
    depth = img_info.image.depth

    if depth == 8:
        # already greyscale. no need to compress
        pass
    elif depth == 16:
        if optimize_float > 1:
            # make into 8bit greyscale
            img_info.size_optimized_mb /= 2
            img_info.optimized_depth = 8
    elif depth == 24:
        if img_info.color_factor < 0.03 * convert_greyscale:
            # make into 8bit greyscale
            img_info.size_optimized_mb /= 3  # 24bit/8bit = 3
            img_info.optimized_depth = 8
    elif depth == 32:
        # check alpha is constant
        if img_info.alpha_factor < 0.5 * convert_greyscale:
            if img_info.color_factor < 0.1 * convert_greyscale:
                # make into 8bit greyscale
                img_info.size_optimized_mb /= 4
                img_info.optimized_depth = 8
            else:
                # remove constant alpha
                img_info.size_optimized_mb -= img_info.size_optimized_mb / 4
                img_info.optimized_depth = 24
    elif depth == 96:
        if img_info.color_factor < 0.03 * convert_greyscale:
            # make into 8bit greyscale
            img_info.size_optimized_mb /= 12  # 24bit/8bit = 3
            img_info.optimized_depth = 8
    elif depth == 128:
        if optimize_float == 1:
            # use to half precision if not already
            if not img_info.image.use_half_precision:
                img_info.size_optimized_mb /= 2
                img_info.read_as_half_precision = True
            else:
                img_info.read_as_half_precision = True
        elif optimize_float > 1:
            if img_info.color_factor < 0.03 * convert_greyscale:
                # make into 8bit greyscale
                img_info.size_optimized_mb /= 8  # 64bit/8bit = 16
                img_info.optimized_depth = 8

    else:
        print(f"Cannot handle bit depth {depth} for {img_info.image.name}")

    return img_info


def compute_image_size(img_info):
    img = img_info.image
    w, h = img.size[0], img.size[1]

    # calc original size
    if img.is_float:
        if img.use_half_precision:
            size_original_mb = w * h * img.depth / 8 / 1024 / 1024 / 2
        else:
            size_original_mb = w * h * img.depth / 8 / 1024 / 1024
    else:
        size_original_mb = w * h * img.depth / 8 / 1024 / 1024
    img_info.size_original_mb = size_original_mb
    img_info.size_optimized_mb = size_original_mb
    return img_info


def scan_image(img):
    w, h = img.size
    depth = img.depth
    pixel_data = np.zeros((w, h, 4), "f")
    img.pixels.foreach_get(pixel_data.ravel())

    img_info = ImageInfo(img, img.filepath)

    if img.packed_file:
        # because we can't optimize packed images
        print(f"Can't optimize packed {img.name}")
        return img_info

    if img.source == "SEQUENCE" or img.source == "MOVIE" or img.source == "TILED" or img.source == "GENERATED":
        # because we can't optimize image sequences
        print(f"Can't optimize none-file images {img.name}")
        return img_info

    # calculate sharpness for smart resize
    peak_sharpness = analyze_sharpness(pixel_data)
    img_info.sharpness_factor = peak_sharpness

    # calculate rgb and alpha value for smart conversion
    color_factor, alpha_factor, range_factor = analyze_rgba(pixel_data)
    img_info.color_factor = color_factor
    img_info.alpha_factor = alpha_factor
    img_info.range_factor = range_factor

    return img_info


def update_memory_usage(self, context):
    """Update the memory usage for each image in the list."""

    settings = {
        "convert_greyscale": context.scene.TC_convert_greyscale,
        "smart_resize": context.scene.TC_smart_resize,
        "optimize_float": context.scene.TC_optimize_float,
    }

    for img_info in context.scene.TC_texture_metadata:
        img_nfo = compute_image_size(img_info)
        img_info = optimize_size(img_info, settings)
        img_info = optimize_depth(img_info, settings)


def optimize_images(self, context):
    """Optimize all textures in the list."""
    for img_info in context.scene.TC_texture_metadata:
        pro.optimize(img_info)

    # set the flag to use optimized textures
    context.scene.TC_texture_swap = "1"


def update_texture_swap(self, context):
    if context.scene.TC_texture_swap == "0":
        # use original
        pro.use_original(context.scene.TC_texture_metadata)
    else:
        # use optimized
        pro.use_optimized(context.scene.TC_texture_metadata)


def generate_html_report(image_info_list, show_optimized=True):
    optimized_images = [info for info in image_info_list if info.size_optimized_mb < info.size_original_mb]

    # Sort by original size in descending order
    all_images_sorted = sorted(image_info_list, key=lambda x: x.size_original_mb, reverse=True)

    total_before, total_after, delta, changes = tally_sizes(all_images_sorted)

    rows = ""
    for info in all_images_sorted:
        original_resolution = f"{info.image.size[0]}x{info.image.size[1]}"
        new_resolution = (
            f"{info.optimized_resolution[0]}x{info.optimized_resolution[1]}"
            if info.optimized_resolution
            else original_resolution
        )

        if info.image.is_float and info.image.use_half_precision:
            original_bit_depth = f"{info.image.depth}bit(½)"
        else:
            original_bit_depth = f"{info.image.depth}bit"

        if info.image.is_float and info.read_as_half_precision:
            new_bit_depth = f"{info.optimized_depth}bit(½)" if info.optimized_depth else f"{info.image.depth}bit(½)"
        else:
            new_bit_depth = f"{info.optimized_depth}bit" if info.optimized_depth else f"{info.image.depth}bit"

        if info.image.packed_file:
            name = f'<span title="Cannot optimize packed images">🔒{info.image.name}</span>'
        else:
            name = f"<span>{info.image.name}</span>"
        size_percentage = int((info.size_original_mb / total_before) * 100)
        rows += web.row_template.format(
            name=name,
            filepath=os.path.abspath(bpy.path.abspath(info.image.filepath_raw, library=info.image.library)).replace(
                "\\", "\\\\"
            ),  # Escape backslashes for JavaScript
            size_original=info.size_original_mb,
            size_optimized=info.size_optimized_mb,
            original_bit_depth=original_bit_depth,
            new_bit_depth=new_bit_depth,
            original_resolution=original_resolution,
            new_resolution=new_resolution,
            highlight="optimized" if info in optimized_images else "",
            size_percentage=size_percentage,
        )

    total_savings = f"Before: {int(total_before)}MB | After: {int(total_after)}MB | Potential Savings: {int(delta)}MB"
    BLURB = """ <a href="https://mikepan.com/">Texture Compactor</a>"""
    notes = f"Report Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')} by {BLURB}"

    return web.html_template.format(
        rows=rows,
        total_savings=total_savings,
        notes=notes,
        checked="checked" if show_optimized else "",
    )


def show_report(image_list):
    filename = bpy.path.abspath(f"//{bpy.data.filepath}_texture_compactor_report.html")

    report = generate_html_report(image_list)
    with open(filename, "w") as file:
        file.write(report)

    # Open the report in the default web browser
    import webbrowser

    webbrowser.open(filename)
