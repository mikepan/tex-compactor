import numpy as np
import time

from texturecompactor import settings

# TODO: 16/32 bit float images
# TODO: image sequence support
# TODO: UDIM TILES
# TODO: persistent data storage and file loading handler
# TODO: better packed image handling
# TODO: eevee support via dxt compression??


class ImageInfo:
    def __init__(self, image, path):
        self.image = image
        self.original_path = path
        self.optimized_path = None
        self.sharpness_factor = 100
        self.color_factor = 100
        self.alpha_factor = 100
        self.size_original_mb = 0
        self.size_optimized_mb = 0


def is_optimized(image_list):
    """Check if any images have been optimized."""
    return any([i.optimized_path is not None for i in image_list])


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

    return color_factor, alpha_factor


def optimize_sharpness(img_info, settings, execute=False):
    smart_resize = float(settings["smart_resize"])

    if img_info.sharpness_factor < 0.1 * smart_resize:
        img_info.size_optimized_mb /= 64
        print(f"Resizable to 1/8th {img_info.image.name}")
    elif img_info.sharpness_factor < 0.2 * smart_resize:
        img_info.size_optimized_mb /= 16
        print(f"Resizable to 1/4th {img_info.image.name}")
    elif img_info.sharpness_factor < 0.4 * smart_resize:
        img_info.size_optimized_mb /= 4
        print(f"Resizable to 1/2 {img_info.image.name}")
    return img_info


def optimize_rgba(img_info, settings, execute=False):
    convert_greyscale = float(settings["convert_greyscale"])
    optimize_float = float(settings["optimize_float"])
    depth = img_info.image.depth

    if depth == 8 or depth == 16:
        # already greyscale. no need to compress
        print(f"single channel: {img_info.image.name}")
    elif depth == 24:
        # print(img_info.color_factor, img_info.image.name)
        if img_info.color_factor < 0.1 * convert_greyscale:
            # make into 8bit greyscale
            print(f"Compressable {img_info.image.name}")
            img_info.size_optimized_mb /= 3  # 24bit/8bit = 3
        else:
            # compress to dxt1
            # print(f"Compressable to DXT1 {img.name}")
            # size_optimized_mb = size_optimized_mb / 6  # Approximate DXT1 compression ratio
            pass

    else:
        print(f"Unknown bit depth {depth} for {img_info.image.name}")

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
        print(f"Packed {img.name}")
        return img_info

    # calculate sharpness for smart resize
    peak_sharpness = analyze_sharpness(pixel_data)
    # print(f"sharpness: {peak_sharpness} {img.name}")
    img_info.sharpness_factor = peak_sharpness

    # calculate rgb and alpha value for smart conversion
    color_factor, alpha_factor = analyze_rgba(pixel_data)
    img_info.color_factor = color_factor
    img_info.alpha_factor = alpha_factor
    # print(f"Color: {color_factor} Alpha: {alpha_factor} {img.name}")

    return img_info


def update_memory_usage(self, context):
    """Update the memory usage for each image in the list."""

    settings = {
        "convert_greyscale": context.scene.TC_convert_greyscale,
        "smart_resize": context.scene.TC_smart_resize,
        "optimize_float": context.scene.TC_optimize_float,
    }

    for img_info in context.scene.TC_texture_metadata:
        img_info = compute_image_size(img_info)
        img_info = optimize_sharpness(img_info, settings)
        img_info = optimize_rgba(img_info, settings)


def generate_html_report(image_info_list, show_optimized=True):
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Optimization Report</title>
    <style>
        html{{
            scrollbar-gutter: stable;
        }}
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #eee;
            color: #333;
        }}
        h1, .total-savings {{
            text-align: center;
            color: #333;
        }}
        table {{
            width: 80%;
            border-collapse: collapse;
            margin: 20px auto;
            background-color: #fff;
        }}
        th, td {{
            padding: 12px;
            border: 1px solid #ddd;
            text-align: right;
        }}
        th {{
            background-color: #f4f4f4;
            font-weight: bold;
            text-align: center;
        }}
        th:nth-child(1) {{
            width: 30%;
        }}
        th:nth-child(2) {{
            width: 10%;
        }}
        th:nth-child(3) {{
            width: 20%;
        }}
        th:nth-child(4) {{
            width: 10%;
        }}
        th:nth-child(5) {{
            width: 10%;
        }}
        .optimized {{
            background-color: #ddeedd;
        }}
        .copy-icon {{
            cursor: pointer;
            margin-left: 5px;
        }}
        .toggle-button {{
            margin: 20px;
            text-align: center;
        }}
    </style>
    <script>
        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(function() {{
                console.log('Copied to clipboard successfully!');
            }}, function(err) {{
                console.error('Could not copy text: ', err);
            }});
        }}

        function toggleImages() {{
            var showOptimized = document.getElementById('toggleButton').checked;
            var rows = document.getElementsByClassName('image-row');
            for (var i = 0; i < rows.length; i++) {{
                if (!showOptimized) {{
                    rows[i].style.display = 'table-row';
                }} else {{
                    if (rows[i].classList.contains('optimized')) {{
                        rows[i].style.display = 'table-row';
                    }} else {{
                        rows[i].style.display = 'none';
                    }}
                }}
            }}
        }}
    </script>
</head>
<body onload="toggleImages()">
    <h1>Texture Compactor Scanning Report</h1>
    <div class="total-savings">
        {total_savings}
    </div>
    <div class="toggle-button">
        <label><input type="checkbox" id="toggleButton" onchange="toggleImages()" {checked}>Only Show Images Available for Optimization</label>
    </div>
    <table>
        <thead>
            <tr>
                <th>Image Name</th>
                <th>Bit Depth</th>
                <th>Resolution</th>
                <th>Texture Memory (MB)</th>
                <th>Optimized Memory (MB)</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    <div class="total-savings">
        {notes}
    </div>
</body>
</html>
    """

    row_template = """
<tr class="image-row {highlight}">
    <td title="{filepath}" style="text-align: left;">
        {name}
        <span class="copy-icon" style="text-align: right;" onclick="copyToClipboard('{filepath}')">⧉</span>
    </td>
    <td>{bit_depth}</td>
    <td>{resolution}</td>
    <td style="width: 150px;">
        <div style="width: 100%; height: 18px; display: flex; justify-content: space-between;">
            <div style="background-color: #eee; height:100%; width:{size_percentage:.2f}%"></div>
            <span>{size_original:.2f}</span>
        </div>
    </td>
    <td>{size_optimized:.2f}</td>
</tr>
"""

    optimized_images = [info for info in image_info_list if info.size_optimized_mb < info.size_original_mb]

    # Sort by original size in descending order
    all_images_sorted = sorted(image_info_list, key=lambda x: x.size_original_mb, reverse=True)

    total_before, total_after, delta, changes = tally_sizes(all_images_sorted)

    rows = ""
    for info in all_images_sorted:
        original_resolution = f"{info.image.size[0]}x{info.image.size[1]}"
        resolution = original_resolution

        if info.image.is_float and info.image.use_half_precision:
            bit_depth = f'<span title="Half float">{info.image.depth // 2}bit *&nbsp;</span>'
        elif info.image.is_float and not info.image.use_half_precision:
            bit_depth = f'<span title="Full float">{info.image.depth}bit **</span>'
        else:
            bit_depth = f"{info.image.depth}bit &nbsp;&nbsp;"
        if info.color_factor < 0.1:
            bit_depth = f"{info.image.depth}bit >> 8bit &nbsp;&nbsp;"

        if info.image.packed_file:
            name = f'<span title="Cannot optimize packed images">🔒{info.image.name}</span>'
        else:
            name = f"<span>{info.image.name}</span>"
        size_percentage = int((info.size_original_mb / total_before) * 100)
        rows += row_template.format(
            name=name,
            filepath=info.image.filepath_raw.replace("\\", "\\\\"),  # Escape backslashes for JavaScript
            size_original=info.size_original_mb,
            size_optimized=info.size_optimized_mb,
            bit_depth=bit_depth,
            resolution=resolution,
            highlight="optimized" if info in optimized_images else "",
            size_percentage=size_percentage,
        )

    total_savings = f"Before: {int(total_before)}MB | After: {int(total_after)}MB | Potential Savings: {int(delta)}MB"
    BLURB = """ <a href="https://mikepan.com/">Texture Compactor</a>"""
    notes = f"Report Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')} by {BLURB}"

    return html_template.format(
        rows=rows,
        total_savings=total_savings,
        notes=notes,
        checked="checked" if show_optimized else "",
    )


def show_report(image_list, filename):
    report = generate_html_report(image_list)
    with open(filename, "w") as file:
        file.write(report)

    # Open the report in the default web browser
    import webbrowser

    webbrowser.open(filename)
