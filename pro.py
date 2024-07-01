from texturecompactor import settings
import bpy


def optimize(img_info):
    image = img_info.image

    if img_info.optimized_resolution:
        width = image.size[0]
        height = image.size[1]

        new_width = max(2, img_info.optimized_resolution[0])
        new_height = max(2, img_info.optimized_resolution[1])

        image.scale(new_width, new_height)
        print(f"Resized {image.name} to {new_width}x{new_height}")

    elif img_info.optimized_depth:
        # Save the original settings
        colorspace_original = image.colorspace_settings.name
        image.colorspace_settings.name = "Non-Color"

        # get file extension of filepath
        filepath_original = image.filepath_raw
        ext = filepath_original.split(".")[-1]
        filepath_new = filepath_original.replace(ext, "optimized1.png")

        # deal with library assets
        filepath_new = bpy.path.abspath(filepath_new, library=image.library)

        scene = bpy.context.scene
        # scene.view_settings.view_transform = "Standard"
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "BW"
        scene.render.image_settings.color_depth = "8"
        scene.render.image_settings.compression = 15

        image.save_render(bpy.path.abspath(filepath_new), scene=scene)

        # replace image with new file
        image.filepath_raw = filepath_new
        image.colorspace_settings.name = colorspace_original

        img_info.optimized_path = filepath_new

        img_info.image.reload()


def convert_to_dxt1(image):
    """Convert the given image to DXT1 format using crunch.exe."""
    # get file extension of filepath
    filepath_original = image.filepath_raw
    ext = filepath_original.split(".")[-1]
    # deal with library assets
    filepath_original = bpy.path.abspath(filepath_original, library=image.library)

    cmd = [
        crunch_path,
        "-file",
        filepath_original,
        "-out",
        filepath_original + ".dds",
        "-fileformat",
        "dds",
        "-dxt1",
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"Error compressing {image.name}: {result.stderr}")
        return False

    # Replace image with new file
    image.filepath_raw = filepath_original + ".dds"

    return True


def revert_to_original(image_list):
    for img in image_list:
        img.image.filepath_raw = img.original_path
        img.image.reload()
        print(f"Reverted {img.image.name} to original")


def revert_to_optimized(image_list):
    for img in image_list:
        img.image.filepath_raw = img.optimized_path
        img.image.reload()
        print(f"Reverted {img.image.name} to optimized")
